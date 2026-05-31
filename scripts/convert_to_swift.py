"""
Convert ChartGeometry JSONL to ms-swift conversation format for VLM LoRA training.
Output: JSONL with {messages: [{role, content}], images: [path]} format.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("convert_to_swift")

SYSTEM_PROMPT = """You are a financial chart geometry analyst. Given a candlestick chart image, extract structured geometric features in strict JSON format. Your output must contain exactly these fields:
- trend_lines: array of detected trend lines with slope and touch points
- price_levels: array of support/resistance levels with price and strength
- candle_patterns: array of candlestick patterns (e.g., doji, hammer, engulfing)
- chart_formations: array of chart formations (e.g., head_and_shoulders, triangle)
- volume_signals: array of volume anomalies or confirmations
- regime: one of "trending", "ranging", "volatile", "calm"
Output ONLY valid JSON, no explanation."""

USER_PROMPT = "Analyze this candlestick chart and extract all geometric features as structured JSON."


def convert_to_swift_format(input_jsonl: str, output_jsonl: str, max_samples: int = None):
    """Convert chart geometry JSONL to ms-swift conversation format."""
    inp = Path(input_jsonl)
    if not inp.exists():
        logger.error(f"Input file not found: {input_jsonl}")
        return

    out = Path(output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(inp, "r", encoding="utf-8") as fin, open(out, "w", encoding="utf-8") as fout:
        for line in fin:
            if max_samples and count >= max_samples:
                break
            line = line.strip()
            if not line:
                continue

            sample = json.loads(line)
            image_path = sample.get("image_path", "")
            geometry = sample.get("geometry_json", {})

            if not image_path or not geometry:
                continue

            geometry_str = json.dumps(geometry, ensure_ascii=False)

            swift_sample = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT},
                    {"role": "assistant", "content": geometry_str},
                ],
                "images": [image_path],
            }
            fout.write(json.dumps(swift_sample, ensure_ascii=False) + "\n")
            count += 1

    logger.info(f"Converted {count} samples -> {output_jsonl}")


def main():
    parser = argparse.ArgumentParser(description="Convert ChartGeometry to ms-swift format")
    parser.add_argument("--input", default="data/chart_geometry/train.jsonl")
    parser.add_argument("--output", default="data/chart_geometry/swift_train.jsonl")
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    convert_to_swift_format(args.input, args.output, args.max_samples)


if __name__ == "__main__":
    main()
