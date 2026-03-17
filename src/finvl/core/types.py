"""
Core domain types for FinVL-MAS.
Defines chart geometry, financial structures, and decision output schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class PatternSignificance(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class Implication(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class FormationStage(str, Enum):
    FORMING = "forming"
    CONFIRMED = "confirmed"
    BROKEN = "broken"


class RegimeType(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    TRANSITIONING = "transitioning"


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Conviction(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# ---------------------------------------------------------------------------
# Chart Geometry Components
# ---------------------------------------------------------------------------

@dataclass
class TrendLine:
    direction: TrendDirection
    slope: float
    intercept: float
    r_squared: float = 0.0
    start_idx: int = 0
    end_idx: int = 0
    status: str = "intact"  # intact / broken / tested
    confidence: float = 0.5


@dataclass
class PriceLevel:
    price: float
    level_type: str = "support"  # support / resistance
    strength: float = 0.5
    touch_count: int = 1
    first_touch_idx: int = 0
    last_touch_idx: int = 0


@dataclass
class CandlePattern:
    pattern: str  # e.g. "doji", "hammer", "engulfing_bullish"
    bar_index: int = 0
    significance: PatternSignificance = PatternSignificance.MODERATE
    implication: Implication = Implication.NEUTRAL


@dataclass
class ChartFormation:
    formation_type: str  # e.g. "double_top", "head_and_shoulders", "triangle"
    stage: FormationStage = FormationStage.FORMING
    target_price: Optional[float] = None
    confidence: float = 0.5
    start_idx: int = 0
    end_idx: int = 0


@dataclass
class VolumeSignal:
    signal_type: str  # e.g. "divergence", "climax", "dry_up"
    bar_index: int = 0
    implication: Implication = Implication.NEUTRAL
    description: str = ""


@dataclass
class RegimeState:
    regime: RegimeType = RegimeType.RANGING
    trend_strength: float = 0.0
    volatility_percentile: float = 0.5
    description: str = ""


@dataclass
class ChartGeometry:
    """Complete structured chart geometry extraction."""
    trendlines: List[TrendLine] = field(default_factory=list)
    support_resistance: List[PriceLevel] = field(default_factory=list)
    candlestick_patterns: List[CandlePattern] = field(default_factory=list)
    formations: List[ChartFormation] = field(default_factory=list)
    volume_signals: List[VolumeSignal] = field(default_factory=list)
    regime: RegimeState = field(default_factory=RegimeState)
    overall_bias: Implication = Implication.NEUTRAL
    confidence: float = 0.5
    narrative: str = ""

    def summary(self) -> str:
        parts = []
        if self.trendlines:
            parts.append(f"{len(self.trendlines)} trendline(s)")
        if self.support_resistance:
            parts.append(f"{len(self.support_resistance)} S/R level(s)")
        if self.candlestick_patterns:
            parts.append(f"{len(self.candlestick_patterns)} candle pattern(s)")
        if self.formations:
            parts.append(f"{len(self.formations)} formation(s)")
        if self.volume_signals:
            parts.append(f"{len(self.volume_signals)} volume signal(s)")
        parts.append(f"regime={self.regime.regime.value}")
        parts.append(f"bias={self.overall_bias.value}")
        return ", ".join(parts)


# ---------------------------------------------------------------------------
# Decision Output
# ---------------------------------------------------------------------------

@dataclass
class DecisionOutput:
    """Final trading decision produced by the DecisionPM agent."""
    action: Action = Action.HOLD
    conviction: Conviction = Conviction.LOW
    position_size_pct: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.5
    rationale: str = ""
    key_evidence: List[str] = field(default_factory=list)
    risks_acknowledged: List[str] = field(default_factory=list)
    contradictions_resolved: str = ""
    chart_geometry: Optional[ChartGeometry] = None
    agent_confidences: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Chart Metadata
# ---------------------------------------------------------------------------

@dataclass
class ChartMetadata:
    """Metadata accompanying a rendered chart image."""
    image_path: str = ""
    asset: str = ""
    start_date: str = ""
    end_date: str = ""
    timeframe: str = "daily"
    price_min: float = 0.0
    price_max: float = 0.0
    current_price: float = 0.0
    overlays: List[str] = field(default_factory=list)
