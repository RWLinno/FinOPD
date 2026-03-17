"""
Base agent abstraction for FinVL-MAS financial reasoning agents.
Adapted from MAS4TS BaseAgentTS for financial decision-making context.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentOutput:
    """Structured output from any specialist agent."""

    agent_name: str
    success: bool
    result: Dict[str, Any]
    confidence: float = 0.5
    metadata: Optional[Dict[str, Any]] = None
    reasoning_trace: Optional[str] = None


@dataclass
class MemoryEntry:
    """A single write to shared memory from an agent."""

    agent_name: str
    key: str
    value: Any
    confidence: float = 0.5
    timestamp: Optional[str] = None


class BaseFinAgent(ABC):
    """
    Base class for all FinVL-MAS specialist agents.

    Each agent:
      - receives inputs (chart geometry, shared memory, raw data, etc.)
      - produces structured output with confidence
      - writes relevant findings to shared memory
      - can read from shared memory to see other agents' findings
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self._memory_writes: List[MemoryEntry] = []

    @abstractmethod
    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
        """
        Run this agent's reasoning step.

        Args:
            inputs: Agent-specific inputs (chart geometry, data, etc.)
            memory: Current shared memory snapshot (read-only view).

        Returns:
            AgentOutput with structured result and confidence.
        """
        ...

    def write_to_memory(self, key: str, value: Any, confidence: float = 0.5):
        """Stage a memory write (applied by the orchestrator after process())."""
        self._memory_writes.append(
            MemoryEntry(agent_name=self.name, key=key, value=value, confidence=confidence)
        )

    def flush_memory_writes(self) -> List[MemoryEntry]:
        """Return and clear pending memory writes."""
        writes = list(self._memory_writes)
        self._memory_writes.clear()
        return writes

    def log(self, msg: str, level: str = "info"):
        getattr(logger, level)(f"[{self.name}] {msg}")
