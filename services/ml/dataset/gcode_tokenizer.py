"""
LEGO Factory v3 - G-code Tokenizer
==================================
Canonicalizer + tokenizer + vocab builder for G-code.
"""

from __future__ import annotations
import re
import json
import hashlib
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DEFAULT_SPECIAL = {"PAD": 0, "BOS": 1, "EOS": 2, "UNK": 3, "MASK": 4}
DEFAULT_PRECISION = {
    "X": 1e-3, "Y": 1e-3, "Z": 1e-3,
    "A": 1e-3, "B": 1e-3, "C": 1e-3,
    "I": 1e-4, "J": 1e-4, "K": 1e-4,
    "F": 1.0, "S": 10.0, "R": 1e-4,
    "P": 1e-3, "Q": 1e-3, "E": 1e-4,
}
KEEP_LITERAL = {"G", "M", "T"}
ADDR_CHARS = set(list("XYZABCIJKFSRPQE"))

LINE_COMMENT_SEMI = re.compile(r";.*?$")
LINE_COMMENT_PARENS = re.compile(r"\(.*?\)")
LINE_NUMBER = re.compile(r"(^|\s)N\d+\b", re.IGNORECASE)
CHECKSUM = re.compile(r"\*[-+]?\d+$")
MULTISPACE = re.compile(r"\s+")
WORD_RE = re.compile(r"([A-Z]+)([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)?$")


@dataclass
class TokenizerConfig:
    """Configuration for G-code tokenizer."""
    mode: str = "hybrid"  # 'literal' | 'split' | 'hybrid'
    precision: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PRECISION))
    clip_bins: Dict[str, int] = field(default_factory=dict)
    canonical_decimal_places: int = 4
    ignore_for_pid: set = field(default_factory=lambda: {"F", "S"})
    special: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_SPECIAL))
    vocab_size: int = 50000
    min_freq: int = 1
    dynamic_numbers: bool = False
    bucket_digits: Optional[int] = None


class GCodeTokenizer:
    """G-code tokenizer with canonicalization and vocabulary management."""

    def __init__(self, config: TokenizerConfig, vocab: Optional[Dict[str, int]] = None):
        self.cfg = config
        self.vocab = vocab or dict(self.cfg.special)
        self.inv_vocab = {i: t for t, i in self.vocab.items()}

    def _strip_comments(self, line: str) -> str:
        line = LINE_COMMENT_PARENS.sub("", line)
        line = LINE_COMMENT_SEMI.sub("", line)
        return line

    def _normalize_words(self, parts: List[str]) -> List[str]:
        out = []
        for p in parts:
            p = p.strip().upper()
            if not p:
                continue
            p = CHECKSUM.sub("", p)
            if p in {"/", "%"}:
                continue
            m = re.match(r"^([GMT])0+(\d+)$", p)
            if m:
                p = f"{m.group(1)}{int(m.group(2))}"
            out.append(p)
        return out

    def canonicalize_line(self, line: str) -> Optional[str]:
        """Canonicalize a single G-code line."""
        line = self._strip_comments(line)
        line = LINE_NUMBER.sub(" ", line)
        line = line.strip()
        if not line:
            return None
        line = line.upper()
        line = MULTISPACE.sub(" ", line)
        parts = self._normalize_words(line.split(" "))
        if not parts:
            return None
        return " ".join(parts)

    def canonicalize(self, lines: Iterable[str]) -> List[str]:
        """Canonicalize multiple G-code lines."""
        out = []
        for ln in lines:
            c = self.canonicalize_line(ln)
            if c:
                out.append(c)
        return out

    def _quantize(self, addr: str, value: float) -> int:
        step = self.cfg.precision.get(addr, 1e-3)
        return int(round(value / step))

    def _clip_bin(self, addr: str, b: int) -> int:
        if addr in self.cfg.clip_bins:
            lim = int(self.cfg.clip_bins[addr])
            if b > lim:
                b = lim
            if b < -lim:
                b = -lim
        return b

    def _bucket_value(self, b: int) -> str:
        """Bucket quantized value to first N digits."""
        if self.cfg.bucket_digits is None:
            return str(b)

        if b < 0:
            b_str = str(abs(b))
            if len(b_str) >= self.cfg.bucket_digits:
                return "-" + b_str[:self.cfg.bucket_digits - 1]
            else:
                return "-" + b_str.zfill(self.cfg.bucket_digits - 1)
        else:
            b_str = str(b)
            if len(b_str) >= self.cfg.bucket_digits:
                return b_str[:self.cfg.bucket_digits]
            else:
                return b_str.zfill(self.cfg.bucket_digits)

    def _tokenize_word(self, token: str) -> List[str]:
        m = WORD_RE.match(token)
        if not m:
            return [token]
        head, num = m.group(1), m.group(2)
        if self.cfg.mode == "literal":
            return [token]
        if self.cfg.mode == "split":
            if num is None:
                return [head]
            try:
                val = float(num)
            except Exception:
                return [head, "NUM_UNPARSEABLE"]
            if head in ADDR_CHARS:
                b = self._clip_bin(head, self._quantize(head, val))
                b_str = self._bucket_value(b)
                return [head, f"NUM_{head}_{b_str}"]
            else:
                b = self._quantize(head, val)
                b_str = self._bucket_value(b)
                if head in {"G", "M", "T"} and float(val).is_integer():
                    return [f"{head}{int(val)}"]
                return [head, f"NUM_{head}_{b_str}"]
        if head in {"G", "M", "T"}:
            if num is not None:
                try:
                    val = float(num)
                    if float(val).is_integer():
                        return [f"{head}{int(val)}"]
                except Exception:
                    pass
            return [head] if num is None else [head, f"NUM_{head}_{num}"]
        if num is None or head not in ADDR_CHARS:
            return [token]
        try:
            val = float(num)
        except Exception:
            return [head, "NUM_UNPARSEABLE"]
        b = self._clip_bin(head, self._quantize(head, val))
        b_str = self._bucket_value(b)
        return [head, f"NUM_{head}_{b_str}"]

    def tokenize_canonical(self, canon_lines: List[str]) -> List[str]:
        """Tokenize canonicalized G-code lines."""
        toks: List[str] = []
        for ln in canon_lines:
            for w in ln.split(" "):
                toks.extend(self._tokenize_word(w))
        return toks

    def train_vocab(self, corpus_files: List[Path], vocab_out: Optional[Path] = None) -> Dict[str, int]:
        """Build vocabulary from corpus files."""
        from collections import Counter
        counts = Counter()
        for fp in corpus_files:
            text = fp.read_text(errors="ignore").splitlines()
            canon = self.canonicalize(text)
            toks = self.tokenize_canonical(canon)
            counts.update(toks)
        vocab = dict(self.cfg.special)
        items = sorted(
            [(tok, cnt) for tok, cnt in counts.items() if cnt >= self.cfg.min_freq and tok not in vocab],
            key=lambda x: (-x[1], x[0])
        )
        for tok, _ in items[:max(0, self.cfg.vocab_size - len(vocab))]:
            vocab[tok] = len(vocab)
        self.vocab = vocab
        self.inv_vocab = {i: t for t, i in vocab.items()}
        if vocab_out:
            self.save_vocab(vocab_out)
        return self.vocab

    def save_vocab(self, path: Path) -> None:
        """Save vocabulary to JSON file."""
        cfg_dict = asdict(self.cfg)
        if 'ignore_for_pid' in cfg_dict and isinstance(cfg_dict['ignore_for_pid'], set):
            cfg_dict['ignore_for_pid'] = list(cfg_dict['ignore_for_pid'])
        path.write_text(json.dumps({"config": cfg_dict, "vocab": self.vocab}, indent=2))

    @staticmethod
    def load(path: Path) -> "GCodeTokenizer":
        """Load tokenizer from JSON file."""
        obj = json.loads(path.read_text())
        cfg_data = obj["config"]
        if 'ignore_for_pid' in cfg_data and isinstance(cfg_data['ignore_for_pid'], list):
            cfg_data['ignore_for_pid'] = set(cfg_data['ignore_for_pid'])
        cfg = TokenizerConfig(**cfg_data)
        return GCodeTokenizer(cfg, obj["vocab"])

    def _tok2id(self, tok: str) -> int:
        if tok in self.vocab:
            return self.vocab[tok]
        if self.cfg.dynamic_numbers and tok.startswith("NUM_"):
            self.vocab[tok] = len(self.vocab)
            self.inv_vocab[self.vocab[tok]] = tok
            return self.vocab[tok]
        return self.cfg.special["UNK"]

    def encode(self, lines: Iterable[str], add_bos_eos: bool = True) -> List[int]:
        """Encode G-code lines to token IDs."""
        canon = self.canonicalize(lines)
        toks = self.tokenize_canonical(canon)
        ids = [self.cfg.special["BOS"]] if add_bos_eos else []
        ids.extend(self._tok2id(t) for t in toks)
        if add_bos_eos:
            ids.append(self.cfg.special["EOS"])
        return ids

    def decode(self, ids: List[int]) -> List[str]:
        """Decode token IDs to strings."""
        toks = [self.inv_vocab.get(i, "[UNK]") for i in ids]
        if toks and toks[0] == "BOS":
            toks = toks[1:]
        if toks and toks[-1] == "EOS":
            toks = toks[:-1]
        return toks

    def program_id(self, lines: Iterable[str]) -> str:
        """Generate unique program ID from G-code."""
        canon = self.canonicalize(lines)
        toks = self.tokenize_canonical(canon)
        filtered = []
        for t in toks:
            if t in self.cfg.ignore_for_pid:
                continue
            if t.startswith("NUM_"):
                parts = t.split("_")
                if len(parts) >= 3 and parts[1] in self.cfg.ignore_for_pid:
                    continue
            filtered.append(t)
        joined = " ".join(filtered).encode("utf-8", errors="ignore")
        return hashlib.sha1(joined).hexdigest()
