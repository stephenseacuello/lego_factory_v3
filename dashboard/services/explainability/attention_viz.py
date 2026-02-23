"""
Attention Visualizer - Transformer attention maps.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class AttentionMap:
    """Single attention map from transformer layer."""
    layer: int
    head: int
    attention_weights: np.ndarray
    tokens: List[str]


@dataclass
class AttentionExplanation:
    """Complete attention explanation."""
    attention_maps: List[AttentionMap]
    aggregated_attention: np.ndarray
    tokens: List[str]
    important_tokens: List[Tuple[str, float]]


class AttentionVisualizer:
    """
    Visualize and analyze transformer attention.

    Features:
    - Multi-head attention aggregation
    - Layer-wise analysis
    - Token importance from attention
    - Attention rollout
    """

    def __init__(self, model: Any = None):
        """
        Initialize attention visualizer.

        Args:
            model: Transformer model
        """
        self.model = model
        self._attention_hooks = []

    def set_model(self, model: Any) -> None:
        """Set model to visualize."""
        self.model = model

    def extract_attention(self,
                         inputs: Any,
                         tokens: List[str]) -> AttentionExplanation:
        """
        Extract attention weights from model.

        Args:
            inputs: Model inputs
            tokens: Token strings

        Returns:
            Attention explanation
        """
        attention_maps = []

        try:
            # Try to extract from HuggingFace transformers
            import torch

            if hasattr(self.model, 'config'):
                # HuggingFace model
                outputs = self.model(**inputs, output_attentions=True)
                attentions = outputs.attentions

                for layer_idx, layer_attention in enumerate(attentions):
                    # layer_attention: (batch, heads, seq, seq)
                    attention_np = layer_attention[0].detach().cpu().numpy()

                    for head_idx in range(attention_np.shape[0]):
                        attention_maps.append(AttentionMap(
                            layer=layer_idx,
                            head=head_idx,
                            attention_weights=attention_np[head_idx],
                            tokens=tokens
                        ))

            else:
                # Custom model - try to find attention layers
                attention_maps = self._extract_custom_attention(inputs, tokens)

        except ImportError:
            logger.warning("PyTorch not available, using mock attention")
            attention_maps = self._generate_mock_attention(tokens)

        # Aggregate attention
        aggregated = self._aggregate_attention(attention_maps)
        important = self._get_important_tokens(aggregated, tokens)

        return AttentionExplanation(
            attention_maps=attention_maps,
            aggregated_attention=aggregated,
            tokens=tokens,
            important_tokens=important
        )

    def _extract_custom_attention(self,
                                 inputs: Any,
                                 tokens: List[str]) -> List[AttentionMap]:
        """Extract attention from custom model."""
        attention_maps = []

        # Register hooks to capture attention
        captured_attentions = []

        def attention_hook(module, input, output):
            if isinstance(output, tuple) and len(output) > 1:
                # Assume attention weights are second output
                captured_attentions.append(output[1])

        # Try to find attention layers
        for name, module in self.model.named_modules():
            if 'attention' in name.lower() or 'attn' in name.lower():
                module.register_forward_hook(attention_hook)

        # Forward pass
        with torch.no_grad():
            self.model(inputs)

        # Process captured attentions
        for layer_idx, attn in enumerate(captured_attentions):
            attn_np = attn.detach().cpu().numpy()
            if len(attn_np.shape) == 4:  # (batch, heads, seq, seq)
                for head_idx in range(attn_np.shape[1]):
                    attention_maps.append(AttentionMap(
                        layer=layer_idx,
                        head=head_idx,
                        attention_weights=attn_np[0, head_idx],
                        tokens=tokens
                    ))

        return attention_maps

    def _generate_mock_attention(self, tokens: List[str]) -> List[AttentionMap]:
        """Generate mock attention for testing."""
        n_tokens = len(tokens)
        n_layers = 4
        n_heads = 8

        attention_maps = []
        for layer in range(n_layers):
            for head in range(n_heads):
                # Random attention pattern
                weights = np.random.dirichlet(np.ones(n_tokens), size=n_tokens)
                attention_maps.append(AttentionMap(
                    layer=layer,
                    head=head,
                    attention_weights=weights,
                    tokens=tokens
                ))

        return attention_maps

    def _aggregate_attention(self,
                            attention_maps: List[AttentionMap],
                            method: str = "mean") -> np.ndarray:
        """
        Aggregate attention across layers and heads.

        Args:
            attention_maps: List of attention maps
            method: "mean", "max", or "rollout"

        Returns:
            Aggregated attention matrix
        """
        if not attention_maps:
            return np.array([])

        all_attention = np.stack([am.attention_weights for am in attention_maps])

        if method == "mean":
            return np.mean(all_attention, axis=0)
        elif method == "max":
            return np.max(all_attention, axis=0)
        elif method == "rollout":
            return self._attention_rollout(attention_maps)
        else:
            return np.mean(all_attention, axis=0)

    def _attention_rollout(self, attention_maps: List[AttentionMap]) -> np.ndarray:
        """
        Compute attention rollout across layers.

        Attention rollout accounts for residual connections by
        multiplying attention matrices across layers.
        """
        if not attention_maps:
            return np.array([])

        # Group by layer
        layers = {}
        for am in attention_maps:
            if am.layer not in layers:
                layers[am.layer] = []
            layers[am.layer].append(am.attention_weights)

        # Average heads within each layer
        layer_attention = {}
        for layer_idx, heads in sorted(layers.items()):
            layer_attention[layer_idx] = np.mean(heads, axis=0)

        # Rollout: multiply across layers
        n_tokens = layer_attention[0].shape[0]
        rollout = np.eye(n_tokens)

        for layer_idx in sorted(layer_attention.keys()):
            attn = layer_attention[layer_idx]
            # Add residual connection
            attn_with_residual = 0.5 * attn + 0.5 * np.eye(n_tokens)
            # Normalize
            attn_with_residual = attn_with_residual / attn_with_residual.sum(axis=-1, keepdims=True)
            rollout = rollout @ attn_with_residual

        return rollout

    def _get_important_tokens(self,
                             aggregated: np.ndarray,
                             tokens: List[str],
                             top_k: int = 10) -> List[Tuple[str, float]]:
        """Get most important tokens from aggregated attention."""
        if len(aggregated) == 0:
            return []

        # Sum attention received by each token
        token_importance = np.sum(aggregated, axis=0)
        token_importance = token_importance / token_importance.sum()

        # Get top tokens
        indices = np.argsort(token_importance)[::-1][:top_k]
        return [(tokens[i], float(token_importance[i])) for i in indices]

    def get_layer_analysis(self,
                          explanation: AttentionExplanation) -> Dict[int, np.ndarray]:
        """Get attention patterns per layer."""
        layers = {}
        for am in explanation.attention_maps:
            if am.layer not in layers:
                layers[am.layer] = []
            layers[am.layer].append(am.attention_weights)

        return {
            layer: np.mean(heads, axis=0)
            for layer, heads in layers.items()
        }

    def get_head_analysis(self,
                         explanation: AttentionExplanation,
                         layer: int) -> Dict[int, np.ndarray]:
        """Get attention patterns per head in a layer."""
        heads = {}
        for am in explanation.attention_maps:
            if am.layer == layer:
                heads[am.head] = am.attention_weights
        return heads

    def format_explanation(self, explanation: AttentionExplanation) -> str:
        """Format explanation as readable text."""
        lines = [
            f"Tokens: {' | '.join(explanation.tokens)}",
            f"Number of layers: {len(set(am.layer for am in explanation.attention_maps))}",
            f"Number of heads per layer: {len(set(am.head for am in explanation.attention_maps))}",
            "\nMost attended tokens:"
        ]

        for token, importance in explanation.important_tokens[:10]:
            lines.append(f"  '{token}': {importance:.4f}")

        return "\n".join(lines)
