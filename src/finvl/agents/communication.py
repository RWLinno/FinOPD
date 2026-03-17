"""
Gated cross-attention communication for multi-agent coordination.
Adapted from MAS4TS agent_communication.py for financial reasoning.

Implements: Com(M, h) = M + sigma(Gate) * Attention(Q=M, K=h, V=h)
"""

import math
from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class GatedCrossAttention(nn.Module):
    """
    Gated cross-attention for agent-to-memory communication.
    Memory is updated by attending to agent-specific hidden states,
    modulated by a learned gate that controls information flow.
    """

    def __init__(self, d_model: int, n_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"

        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)

        self.gate_net = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
            nn.Sigmoid(),
        )

        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(d_model)
        self._init_weights()

    def _init_weights(self):
        for module in [self.W_q, self.W_k, self.W_v, self.W_o]:
            nn.init.xavier_uniform_(module.weight, gain=1.0 / math.sqrt(2))
            nn.init.zeros_(module.bias)
        for module in self.gate_net.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight, gain=0.1)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, memory: torch.Tensor, agent_hidden: torch.Tensor) -> torch.Tensor:
        B, L, D = memory.shape

        Q = self.W_q(memory).view(B, L, self.n_heads, self.d_k).transpose(1, 2)
        K = self.W_k(agent_hidden).view(B, L, self.n_heads, self.d_k).transpose(1, 2)
        V = self.W_v(agent_hidden).view(B, L, self.n_heads, self.d_k).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_output = torch.matmul(attn_weights, V)
        attn_output = attn_output.transpose(1, 2).contiguous().view(B, L, D)
        attn_output = self.W_o(attn_output)

        gate = self.gate_net(agent_hidden)
        updated_memory = memory + gate * attn_output
        return self.layer_norm(updated_memory)


class AdaptiveAgentFusion(nn.Module):
    """
    Fuses multiple agent embeddings into shared memory using
    sequential gated cross-attention with optional confidence weighting.
    """

    def __init__(self, d_model: int, max_agents: int = 5, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.attention_modules = nn.ModuleList(
            [GatedCrossAttention(d_model, n_heads=4, dropout=dropout) for _ in range(max_agents)]
        )
        self.layer_norm = nn.LayerNorm(d_model)

    def forward(
        self,
        base_embedding: torch.Tensor,
        agent_embeddings: List[torch.Tensor],
        agent_confidences: Optional[List[float]] = None,
    ) -> torch.Tensor:
        if not agent_embeddings:
            return base_embedding

        fused = base_embedding
        for i, agent_emb in enumerate(agent_embeddings):
            if i >= len(self.attention_modules):
                break
            prev = fused
            fused = self.attention_modules[i](fused, agent_emb)
            if agent_confidences is not None and i < len(agent_confidences):
                alpha = agent_confidences[i]
                fused = (1 - alpha) * prev + alpha * fused
        return fused


class ConfidenceWeightedAggregator(nn.Module):
    """
    Aggregates multiple prediction tensors weighted by learned confidence scores.
    """

    def __init__(self, feature_dim: int):
        super().__init__()
        self.confidence_scorer = nn.Sequential(
            nn.Linear(feature_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, predictions: List[torch.Tensor]) -> torch.Tensor:
        if len(predictions) == 1:
            return predictions[0]

        batch_size = predictions[0].shape[0]
        confidences = []
        for pred in predictions:
            pred_flat = pred.reshape(batch_size, -1)
            conf = self.confidence_scorer(pred_flat)
            confidences.append(conf)

        confidences = torch.cat(confidences, dim=1)
        weights = torch.softmax(confidences, dim=1)

        stacked = torch.stack(predictions, dim=1)
        weights_expanded = weights.unsqueeze(-1).unsqueeze(-1)
        if stacked.dim() == 4:
            return (stacked * weights_expanded).sum(dim=1)
        return (stacked * weights.unsqueeze(-1)).sum(dim=1)
