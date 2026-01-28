"""
LEGO Factory v3 - MM-DTAE-LSTM Model
====================================
Multimodal Deep Transformer Autoencoder + LSTM for sensor-to-gcode fingerprinting.

Components:
- SinePositionalEncoding: sinusoidal positional encoding
- DTAE: denoising Transformer autoencoder for self-supervised robustness
- LinearModalityEncoder: per-modality MLP + LayerNorm + GELU + positional encoding
- CrossModalFusion: learned modality gates + cross-attention (+ modality dropout)
- ContextEmbeddings: sum of small categorical embeddings
- GCodeLMHead: causal Transformer decoder (teacher forcing + greedy generate)
- FingerprintHead: pooled + projected, L2-normalized embedding
- MM_DTAE_LSTM: the full model with all heads
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

__all__ = [
    "ModelConfig",
    "MM_DTAE_LSTM",
    "EnhancedEncoder",
    "make_pad_mask",
]


def make_pad_mask(lengths: torch.Tensor, max_len: Optional[int] = None) -> torch.Tensor:
    """Create boolean mask True at PAD positions."""
    B = lengths.numel()
    T = int(max_len if max_len is not None else int(lengths.max().item()))
    idx = torch.arange(T, device=lengths.device).unsqueeze(0).expand(B, T)
    return idx >= lengths.unsqueeze(1)


class SinePositionalEncoding(nn.Module):
    """Standard sinusoidal positional encoding."""

    def __init__(self, d_model: int, max_len: int = 8192):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, :x.size(1)]


class DTAE(nn.Module):
    """Denoising Transformer AutoEncoder block."""

    def __init__(self, d_model: int, nhead: int = 4, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=4 * d_model,
            dropout=dropout, batch_first=True
        )
        dec_layer = nn.TransformerDecoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=4 * d_model,
            dropout=dropout, batch_first=True
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=num_layers)
        self.decoder = nn.TransformerDecoder(dec_layer, num_layers=num_layers)
        self.pos = SinePositionalEncoding(d_model)
        self.dropout = nn.Dropout(dropout)

    @staticmethod
    def add_noise(x: torch.Tensor, level: float = 0.05, mask_prob: float = 0.1) -> torch.Tensor:
        """Gaussian noise + optional elementwise masking."""
        noise = torch.randn_like(x) * level
        x_noisy = x + noise
        if mask_prob > 0:
            mask = (torch.rand_like(x[..., :1]) < mask_prob).float()
            x_noisy = x_noisy * (1 - mask)
        return x_noisy

    def forward(
        self,
        x: torch.Tensor,
        src_key_padding_mask: Optional[torch.Tensor] = None,
        tgt_len: Optional[int] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, D = x.shape
        x_noisy = self.add_noise(x)
        z = self.encoder(self.pos(self.dropout(x_noisy)), src_key_padding_mask=src_key_padding_mask)
        L = int(tgt_len or T)
        tgt = torch.zeros(B, L, D, device=x.device)
        rec = self.decoder(
            self.pos(tgt), z,
            tgt_key_padding_mask=(src_key_padding_mask[:, :L] if src_key_padding_mask is not None else None),
            memory_key_padding_mask=src_key_padding_mask,
        )
        return rec, z


class LinearModalityEncoder(nn.Module):
    """Two-layer MLP + LayerNorm + GELU + Positional Encoding per modality."""

    def __init__(self, in_dim: int, d_model: int):
        super().__init__()
        self.proj = nn.Sequential(
            nn.Linear(in_dim, d_model), nn.LayerNorm(d_model), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(d_model, d_model), nn.LayerNorm(d_model), nn.GELU(), nn.Dropout(0.1)
        )
        self.pos = SinePositionalEncoding(d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.pos(self.proj(x))


class CrossModalFusion(nn.Module):
    """Fuse modality sequences with learned gates + cross-attention."""

    def __init__(self, d_model: int, n_heads: int, num_modalities: int):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.ln = nn.LayerNorm(d_model)
        self.gates = nn.Parameter(torch.ones(num_modalities))
        self.d_model = d_model
        self.n_heads = n_heads
        self.use_flash = hasattr(F, 'scaled_dot_product_attention')

    def forward(
        self,
        mods: List[torch.Tensor],
        key_padding_mask: Optional[torch.Tensor],
        modality_dropout_p: float = 0.0,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        M = len(mods)
        B, T, D = mods[0].shape
        gates = torch.sigmoid(self.gates[:M])

        drop_mask = torch.ones(M, device=mods[0].device)
        if self.training and modality_dropout_p > 0:
            drop_mask = (torch.rand(M, device=mods[0].device) > modality_dropout_p).float()
            if drop_mask.sum() == 0:
                keep_idx = torch.randint(0, M, (1,), device=mods[0].device)
                drop_mask[keep_idx] = 1.0
        mods = [mods[i] * drop_mask[i] for i in range(M)]

        stack = torch.stack(mods, dim=2)
        q = stack.mean(dim=2)
        kv = stack.flatten(1, 2)

        if key_padding_mask is not None:
            kv_key_padding = key_padding_mask.unsqueeze(1).expand(B, M, T).transpose(1, 2).flatten(1)
        else:
            kv_key_padding = None

        attn_out, _ = self.attn(q, kv, kv, key_padding_mask=kv_key_padding)

        fused = self.ln(q + attn_out)
        gated_sum = sum(gates[i] * mods[i] for i in range(M)) / (gates.sum() + 1e-6)
        fused = self.ln(fused + gated_sum)
        if key_padding_mask is not None:
            fused = fused.masked_fill(key_padding_mask.unsqueeze(-1), 0.0)
        return fused, gates.detach(), drop_mask.detach()


class ContextEmbeddings(nn.Module):
    """Summation of multiple categorical embeddings."""

    def __init__(self, d_model: int, specs: Optional[Dict[str, int]] = None):
        super().__init__()
        self.d_model = d_model
        specs = specs or {}
        self.tables = nn.ModuleDict({k: nn.Embedding(v, d_model) for k, v in specs.items()})

    def forward(self, ctx_ids: Optional[Dict[str, torch.Tensor]], T: int, device) -> torch.Tensor:
        if not ctx_ids or len(self.tables) == 0:
            return torch.zeros(1, 1, self.d_model, device=device) * 0.0
        acc = None
        for name, emb in self.tables.items():
            if name not in ctx_ids:
                continue
            ids = ctx_ids[name].to(device)
            if ids.dim() == 1:
                x = emb(ids).unsqueeze(1).expand(-1, T, -1)
            else:
                x = emb(ids)
            acc = x if acc is None else (acc + x)
        if acc is None:
            return torch.zeros(1, 1, self.d_model, device=device) * 0.0
        return acc


class GCodeLMHead(nn.Module):
    """Causal Transformer decoder with weight tying."""

    def __init__(self, d_model: int, vocab_size: int, nhead: int = 4, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model)
        dec_layer = nn.TransformerDecoderLayer(d_model, nhead, 4 * d_model, dropout, batch_first=True)
        self.decoder = nn.TransformerDecoder(dec_layer, num_layers=num_layers)
        self.pos = SinePositionalEncoding(d_model)
        self.proj = nn.Linear(d_model, vocab_size, bias=False)
        self.proj.weight = self.embed.weight

    @staticmethod
    def causal_mask(sz: int, device) -> torch.Tensor:
        return torch.triu(torch.ones(sz, sz, device=device), diagonal=1).bool()

    def forward(self, memory: torch.Tensor, tgt_tokens: torch.Tensor) -> torch.Tensor:
        x = self.pos(self.embed(tgt_tokens))
        mask = self.causal_mask(x.size(1), x.device)
        dec = self.decoder(tgt=x, memory=memory, tgt_mask=mask)
        return self.proj(dec)

    @torch.no_grad()
    def generate(self, memory: torch.Tensor, max_len: int, bos_id: int = 1) -> torch.Tensor:
        B = memory.size(0)
        out = torch.full((B, 1), bos_id, dtype=torch.long, device=memory.device)
        for _ in range(max_len):
            x = self.pos(self.embed(out))
            mask = self.causal_mask(x.size(1), x.device)
            dec = self.decoder(tgt=x, memory=memory, tgt_mask=mask)
            logits = self.proj(dec[:, -1:])
            nxt = torch.argmax(logits, dim=-1)
            out = torch.cat([out, nxt], dim=1)
        return out[:, 1:]


class FingerprintHead(nn.Module):
    """Fingerprint head with attention pooling."""

    def __init__(self, d_model: int, out_dim: int = 128, use_attention_pooling: bool = True):
        super().__init__()
        self.use_attention_pooling = use_attention_pooling
        self.d_model = d_model

        if use_attention_pooling:
            self.query = nn.Parameter(torch.randn(1, 1, d_model))
            self.attn_pool = nn.MultiheadAttention(d_model, num_heads=1, batch_first=True)
            nn.init.xavier_uniform_(self.query)

        self.proj = nn.Sequential(
            nn.Linear(d_model, d_model), nn.GELU(),
            nn.Linear(d_model, out_dim)
        )

    def forward(self, seq_latent: torch.Tensor, key_padding_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        if self.use_attention_pooling:
            B = seq_latent.size(0)
            query = self.query.expand(B, -1, -1)
            pooled, _ = self.attn_pool(query, seq_latent, seq_latent, key_padding_mask=key_padding_mask)
            fp = pooled.squeeze(1)
        else:
            if key_padding_mask is not None:
                mask = (~key_padding_mask).unsqueeze(-1).float()
                fp = (seq_latent * mask).sum(dim=1) / (mask.sum(dim=1) + 1e-8)
            else:
                fp = seq_latent.mean(dim=1)

        fp = self.proj(fp)
        return F.normalize(fp, dim=-1)


@dataclass
class ModelConfig:
    """Configuration for MM-DTAE-LSTM model."""
    sensor_dims: List[int]
    d_model: int = 256
    lstm_layers: int = 2
    gcode_vocab: int = 128
    future_len: int = 8
    n_heads: int = 4
    dropout: float = 0.1
    context_specs: Optional[Dict[str, int]] = None
    fp_dim: int = 128
    use_attention_pooling: bool = True


class MM_DTAE_LSTM(nn.Module):
    """Backbone: per-modality encoders → modality+context fusion → DTAE → LSTM → heads."""

    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        self.encoders = nn.ModuleList([
            LinearModalityEncoder(d, config.d_model) for d in config.sensor_dims
        ])
        self.mod_emb = nn.Embedding(len(config.sensor_dims), config.d_model)
        self.fusion = CrossModalFusion(config.d_model, config.n_heads, num_modalities=len(config.sensor_dims))
        self.dtae = DTAE(config.d_model, nhead=config.n_heads, dropout=config.dropout)
        self.temporal = nn.LSTM(
            config.d_model, config.d_model, num_layers=config.lstm_layers,
            batch_first=True, dropout=config.dropout
        )
        self.norm = nn.LayerNorm(config.d_model)
        self.ctx = ContextEmbeddings(config.d_model, config.context_specs or {})

        # Heads
        self.head_cls = nn.Linear(config.d_model, 5)
        self.head_reg = nn.Linear(config.d_model, 3)
        self.head_anom = nn.Linear(config.d_model, 1)
        self.head_future = nn.Sequential(
            nn.Linear(config.d_model, config.d_model), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(config.d_model, config.future_len * config.d_model)
        )
        self.gcode_head = GCodeLMHead(config.d_model, config.gcode_vocab, nhead=config.n_heads)
        self.fp_head = FingerprintHead(config.d_model, out_dim=config.fp_dim,
                                        use_attention_pooling=config.use_attention_pooling)

    def forward(
        self,
        mods: List[torch.Tensor],
        lengths: torch.Tensor,
        gcode_in: Optional[torch.Tensor] = None,
        modality_dropout_p: float = 0.0,
        ctx_ids: Optional[Dict[str, torch.Tensor]] = None,
    ) -> Dict[str, torch.Tensor]:
        pad_mask = make_pad_mask(lengths, max_len=mods[0].size(1))
        encoded_mods = []
        for i, (enc, m) in enumerate(zip(self.encoders, mods)):
            e = enc(m)
            e = e + self.mod_emb.weight[i].view(1, 1, -1)
            encoded_mods.append(e)

        fused, gates, drop_mask = self.fusion(
            encoded_mods, key_padding_mask=pad_mask, modality_dropout_p=modality_dropout_p
        )
        fused = fused + self.ctx(ctx_ids, T=fused.size(1), device=fused.device)

        rec, z = self.dtae(fused, src_key_padding_mask=pad_mask)
        lstm_out, _ = self.temporal(z)
        lstm_out = self.norm(lstm_out)

        last_idx = (lengths.clamp(min=1) - 1).view(-1)
        last = lstm_out[torch.arange(lstm_out.size(0), device=lstm_out.device), last_idx]

        out: Dict[str, torch.Tensor] = {
            "recon": rec,
            "cls": self.head_cls(last),
            "reg": self.head_reg(last),
            "anom": self.head_anom(last),
            "future": self.head_future(last).view(last.size(0), self.config.future_len, -1),
            "gates": gates,
            "drop_mask": drop_mask,
            "memory": lstm_out,
            "encoded_mods": torch.stack([m.detach() for m in encoded_mods], dim=2),
        }
        if gcode_in is not None:
            out["gcode_logits"] = self.gcode_head(lstm_out, gcode_in)

        out["fingerprint"] = self.fp_head(lstm_out, key_padding_mask=pad_mask)
        return out

    def to_config_dict(self) -> Dict:
        return asdict(self.config)

    @staticmethod
    def count_params(model: nn.Module) -> int:
        return sum(p.numel() for p in model.parameters() if p.requires_grad)


class MultiHeadAttentionPooling(nn.Module):
    """Multi-head attention pooling with learned query vectors."""

    def __init__(
        self,
        hidden_dim: int,
        n_heads: int = 4,
        n_queries: int = 8,
        dropout: float = 0.1,
        output_dim: Optional[int] = None,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.n_queries = n_queries
        self.n_heads = n_heads
        self.output_dim = output_dim or hidden_dim

        self.queries = nn.Parameter(torch.randn(n_queries, hidden_dim) * 0.02)
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim, num_heads=n_heads, dropout=dropout, batch_first=True
        )
        self.out_proj = nn.Linear(hidden_dim * n_queries, self.output_dim)
        self.layer_norm = nn.LayerNorm(self.output_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        batch_size = x.size(0)
        queries = self.queries.unsqueeze(0).expand(batch_size, -1, -1)
        attn_out, _ = self.attention(queries, x, x, key_padding_mask=mask)
        pooled = attn_out.reshape(batch_size, -1)
        pooled = self.out_proj(pooled)
        pooled = self.layer_norm(pooled)
        pooled = self.dropout(pooled)
        return pooled


class MultiScaleTemporalEncoder(nn.Module):
    """Enhanced encoder with multi-scale temporal convolutions."""

    def __init__(
        self,
        input_dim: int = 155,
        hidden_dim: int = 256,
        latent_dim: int = 128,
        n_scales: int = 4,
        kernel_sizes: Optional[List[int]] = None,
        dilations: Optional[List[int]] = None,
        lstm_layers: int = 2,
        dropout: float = 0.3,
        use_multihead_pooling: bool = True,
        pooling_n_heads: int = 4,
        pooling_n_queries: int = 8,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.n_scales = n_scales

        kernel_sizes = kernel_sizes or [3, 5, 7, 11]
        dilations = dilations or [1, 2, 4, 8]

        self.kernel_sizes = kernel_sizes
        self.dilations = dilations

        branch_dim = hidden_dim // n_scales
        self.conv_branches = nn.ModuleList()
        for k, d in zip(kernel_sizes, dilations):
            padding = (k - 1) * d // 2
            branch = nn.Sequential(
                nn.Conv1d(input_dim, branch_dim, kernel_size=k, dilation=d, padding=padding),
                nn.BatchNorm1d(branch_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            )
            self.conv_branches.append(branch)

        self.fusion = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=1),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
        )

        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if lstm_layers > 1 else 0,
        )

        self.proj = nn.Sequential(
            nn.Linear(hidden_dim * 2, latent_dim),
            nn.LayerNorm(latent_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.use_multihead_pooling = use_multihead_pooling
        if use_multihead_pooling:
            self.pooling = MultiHeadAttentionPooling(
                hidden_dim=latent_dim,
                n_heads=pooling_n_heads,
                n_queries=pooling_n_queries,
                dropout=dropout,
                output_dim=latent_dim,
            )
        else:
            self.pooling_query = nn.Parameter(torch.randn(1, 1, latent_dim) * 0.02)
            self.pooling_attn = nn.MultiheadAttention(latent_dim, num_heads=1, batch_first=True)

    def forward(
        self,
        x: torch.Tensor,
        lengths: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, C = x.shape
        x_conv = x.transpose(1, 2)
        branch_outs = [branch(x_conv) for branch in self.conv_branches]
        x_multi = torch.cat(branch_outs, dim=1)
        x_fused = self.fusion(x_multi)
        x_seq = x_fused.transpose(1, 2)

        if lengths is not None:
            lengths_clamped = lengths.clamp(min=1, max=T).cpu()
            x_packed = nn.utils.rnn.pack_padded_sequence(
                x_seq, lengths_clamped, batch_first=True, enforce_sorted=False
            )
            lstm_out, _ = self.lstm(x_packed)
            lstm_out, _ = nn.utils.rnn.pad_packed_sequence(lstm_out, batch_first=True, total_length=T)
        else:
            lstm_out, _ = self.lstm(x_seq)

        memory = self.proj(lstm_out)

        pad_mask = None
        if lengths is not None:
            pad_mask = make_pad_mask(lengths, max_len=T)

        if self.use_multihead_pooling:
            features = self.pooling(memory, mask=pad_mask)
        else:
            query = self.pooling_query.expand(B, -1, -1)
            features, _ = self.pooling_attn(query, memory, memory, key_padding_mask=pad_mask)
            features = features.squeeze(1)

        return features, memory


class EnhancedEncoder(nn.Module):
    """Enhanced encoder combining multi-scale temporal convolutions and attention pooling."""

    def __init__(
        self,
        input_dim: int = 155,
        hidden_dim: int = 256,
        latent_dim: int = 128,
        n_operations: int = 9,
        use_multiscale: bool = True,
        n_scales: int = 4,
        kernel_sizes: Optional[List[int]] = None,
        dilations: Optional[List[int]] = None,
        lstm_layers: int = 2,
        use_multihead_pooling: bool = True,
        pooling_n_heads: int = 4,
        pooling_n_queries: int = 8,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.use_multiscale = use_multiscale

        if use_multiscale:
            self.temporal_encoder = MultiScaleTemporalEncoder(
                input_dim=input_dim,
                hidden_dim=hidden_dim,
                latent_dim=latent_dim,
                n_scales=n_scales,
                kernel_sizes=kernel_sizes,
                dilations=dilations,
                lstm_layers=lstm_layers,
                dropout=dropout,
                use_multihead_pooling=use_multihead_pooling,
                pooling_n_heads=pooling_n_heads,
                pooling_n_queries=pooling_n_queries,
            )

        self.classifier = nn.Sequential(
            nn.Linear(latent_dim, latent_dim // 2),
            nn.LayerNorm(latent_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(latent_dim // 2, n_operations),
        )

    def encode(
        self,
        x: torch.Tensor,
        lengths: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.temporal_encoder(x, lengths)

    def forward(
        self,
        x: torch.Tensor,
        lengths: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        features, memory = self.encode(x, lengths)
        cls_logits = self.classifier(features)

        return {
            'features': features,
            'memory': memory,
            'cls_logits': cls_logits,
        }
