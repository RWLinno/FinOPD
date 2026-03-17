"""
ChartAnalystAgent: Perceives and describes visual chart geometry.
Combines rule-based geometry extraction with optional VLM analysis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from finvl.agents.base import AgentOutput, BaseFinAgent
from finvl.core.types import ChartGeometry
from finvl.visual.candlestick import CandlestickClassifier
from finvl.visual.formations import FormationDetector
from finvl.visual.geometry import GeometryExtractor
from finvl.visual.vlm_parser import parse_vlm_chart_analysis

logger = logging.getLogger(__name__)


class ChartAnalystAgent(BaseFinAgent):
    """
    Perceives chart geometry via rule-based extraction and optional VLM.
    Writes extracted ChartGeometry and narrative to shared memory.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__("ChartAnalyst", config or {})
        geo_cfg = config.get("geometry", {}) if config else {}
        self.geometry_extractor = GeometryExtractor(geo_cfg)
        self.candlestick_classifier = CandlestickClassifier()
        self.formation_detector = FormationDetector()
        self.use_vlm = (config or {}).get("use_vlm", False)
        self.use_rule_based = (config or {}).get("use_rule_based", True)

    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
        df = inputs.get("ohlcv_df")
        if df is None or len(df) == 0:
            return AgentOutput(
                agent_name=self.name, success=False,
                result={}, confidence=0.0,
                reasoning_trace="No OHLCV data provided",
            )

        # Rule-based geometry extraction
        rule_geometry = ChartGeometry()
        if self.use_rule_based:
            rule_geometry = self.geometry_extractor.extract(df)
            extra_candles = self.candlestick_classifier.classify(df)
            rule_geometry.candlestick_patterns.extend(extra_candles)
            extra_formations = self.formation_detector.detect(df)
            rule_geometry.formations.extend(extra_formations)

        # VLM-based analysis (if enabled and image available)
        vlm_geometry = None
        if self.use_vlm and inputs.get("chart_image_path"):
            vlm_client = inputs.get("vlm_client")
            if vlm_client:
                try:
                    from finvl.utils.prompts import get_system_prompt, render_prompt
                    sys_prompt = get_system_prompt("chart_analyst", "chart_analysis")
                    user_prompt = render_prompt(
                        "chart_analyst", "chart_analysis", "user_template",
                        {
                            "asset": inputs.get("asset", "ASSET"),
                            "timeframe": inputs.get("timeframe", "daily"),
                            "start_date": inputs.get("start_date", ""),
                            "end_date": inputs.get("end_date", ""),
                            "current_price": inputs.get("current_price", 0),
                            "rule_based_geometry": rule_geometry.summary(),
                        },
                    )
                    vlm_result = await vlm_client.analyze_chart(
                        inputs["chart_image_path"], sys_prompt, user_prompt
                    )
                    vlm_geometry = parse_vlm_chart_analysis(vlm_result)
                except Exception as e:
                    logger.warning(f"VLM analysis failed, using rule-based only: {e}")
                    vlm_geometry = None

        # Merge: prefer rule-based for precise values, VLM for narrative and formations
        final = self._merge_geometries(rule_geometry, vlm_geometry)

        self.write_to_memory("chart_geometry", final, confidence=final.confidence)
        self.write_to_memory("chart_narrative", final.narrative, confidence=final.confidence)
        self.write_to_memory("chart_bias", final.overall_bias.value, confidence=final.confidence)

        return AgentOutput(
            agent_name=self.name,
            success=True,
            result={
                "geometry_summary": final.summary(),
                "bias": final.overall_bias.value,
                "regime": final.regime.regime.value,
                "narrative": final.narrative,
                "trendlines": len(final.trendlines),
                "sr_levels": len(final.support_resistance),
                "patterns": len(final.candlestick_patterns),
                "formations": len(final.formations),
            },
            confidence=final.confidence,
            reasoning_trace=f"Extracted geometry: {final.summary()}",
        )

    def _merge_geometries(
        self, rule: ChartGeometry, vlm: ChartGeometry | None
    ) -> ChartGeometry:
        if vlm is None:
            return rule

        # Start with rule-based formations as the base, then add
        # VLM-discovered formations that the rule system did not detect.
        merged_formations = list(rule.formations)
        rule_types = {f.formation_type for f in rule.formations}
        for f in vlm.formations:
            if f.formation_type not in rule_types:
                merged_formations.append(f)

        merged = ChartGeometry(
            trendlines=rule.trendlines,
            support_resistance=rule.support_resistance,
            candlestick_patterns=rule.candlestick_patterns,
            formations=merged_formations,
            volume_signals=rule.volume_signals,
            regime=rule.regime,
            overall_bias=vlm.overall_bias if vlm.confidence > 0.3 else rule.overall_bias,
            confidence=max(rule.confidence, vlm.confidence),
            narrative=vlm.narrative if vlm.narrative else rule.narrative,
        )

        return merged
