"""
Shared memory system for FinVL-MAS multi-agent coordination.
Supports both structured (dict-based) and tensor-level memory
with confidence tracking, disagreement detection, and gated updates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MemorySlot:
    """A single typed slot in shared memory."""
    value: Any = None
    confidence: float = 0.0
    source_agent: str = ""
    timestamp: int = 0  # step index


class SharedMemory:
    """
    Structured shared memory for multi-agent coordination.

    Provides:
    - Confidence-weighted writes: high-confidence agents have more influence
    - History tracking: keeps previous values for disagreement detection
    - Disagreement detection: flags when agents contradict each other
    """

    def __init__(self):
        self._slots: Dict[str, MemorySlot] = {}
        self._history: Dict[str, List[MemorySlot]] = {}
        self._step: int = 0

    def write(self, key: str, value: Any, confidence: float, source: str):
        """Write or update a memory slot with confidence gating."""
        slot = MemorySlot(
            value=value, confidence=confidence,
            source_agent=source, timestamp=self._step,
        )
        if key not in self._history:
            self._history[key] = []
        if key in self._slots:
            self._history[key].append(self._slots[key])

        existing = self._slots.get(key)
        if existing is None or confidence >= existing.confidence:
            self._slots[key] = slot
        else:
            # Lower confidence: still record but don't overwrite
            self._history[key].append(slot)

    def read(self, key: str, default: Any = None) -> Any:
        """Read a value from memory."""
        slot = self._slots.get(key)
        return slot.value if slot else default

    def read_with_confidence(self, key: str) -> Tuple[Any, float]:
        """Read value and its confidence."""
        slot = self._slots.get(key)
        if slot:
            return slot.value, slot.confidence
        return None, 0.0

    def as_dict(self) -> Dict[str, Any]:
        """Export memory as a flat dict (for agent consumption)."""
        result = {}
        for key, slot in self._slots.items():
            result[key] = slot.value
            result[f"_confidence_{key}"] = slot.confidence
        return result

    def detect_disagreements(self) -> List[str]:
        """
        Detect disagreements: cases where different agents wrote
        conflicting values for related keys.
        """
        disagreements = []

        # Check bias-type keys for contradictions
        bias_keys = [k for k in self._slots if "bias" in k]
        bias_values = {}
        for k in bias_keys:
            slot = self._slots[k]
            if slot.confidence > 0.2:
                bias_values[k] = (slot.value, slot.confidence, slot.source_agent)

        vals = list(bias_values.values())
        for i, (v1, c1, s1) in enumerate(vals):
            for v2, c2, s2 in vals[i + 1:]:
                if self._are_contradictory(v1, v2) and min(c1, c2) > 0.3:
                    disagreements.append(
                        f"{s1} says '{v1}' vs {s2} says '{v2}'"
                    )
        return disagreements

    @staticmethod
    def _are_contradictory(v1: Any, v2: Any) -> bool:
        """Check if two bias values are contradictory."""
        if isinstance(v1, str) and isinstance(v2, str):
            contradictions = {
                ("bullish", "bearish"), ("bearish", "bullish"),
            }
            return (v1.lower(), v2.lower()) in contradictions
        return False

    def advance_step(self):
        """Advance the internal step counter."""
        self._step += 1

    def clear(self):
        """Reset memory for a new decision episode."""
        self._slots.clear()
        self._history.clear()
        self._step = 0

    @property
    def keys(self) -> List[str]:
        return list(self._slots.keys())

    def summary(self) -> str:
        parts = []
        for key, slot in self._slots.items():
            val_repr = str(slot.value)[:60]
            parts.append(f"  {key}: {val_repr} (conf={slot.confidence:.2f}, src={slot.source_agent})")
        return "SharedMemory:\n" + "\n".join(parts) if parts else "SharedMemory: empty"


class TraceMemory:
    """
    Cross-episode memory that stores historical decisions and outcomes
    for the R&D loop's iterative refinement.
    """

    def __init__(self, max_entries: int = 1000):
        self.entries: List[Dict[str, Any]] = []
        self.max_entries = max_entries

    def record(self, date: str, decision: Any, outcome: Dict[str, Any],
               memory_snapshot: Dict[str, Any]):
        entry = {
            "date": date,
            "decision": decision,
            "outcome": outcome,
            "memory_snapshot": memory_snapshot,
        }
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        return self.entries[-n:]

    def win_rate(self) -> float:
        if not self.entries:
            return 0.0
        wins = sum(1 for e in self.entries if e["outcome"].get("pnl", 0) > 0)
        return wins / len(self.entries)
