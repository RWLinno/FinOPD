"""
Evaluate VLM LoRA checkpoint on chart geometry extraction.
Reports pattern-level recall/precision and regime accuracy.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_vlm_lora")


def parse_json_output(text: str) -> Dict[str, Any]:
    """Try to parse JSON from model output, handling common issues."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return {}
    return {}


def compute_metrics(predictions: List[Dict], ground_truths: List[Dict]) -> Dict[str, float]:
    """Compute evaluation metrics for geometry extraction."""
    regime_correct = 0
    regime_total = 0
    json_valid = 0
    total = len(predictions)

    pattern_tp = 0
    pattern_fp = 0
    pattern_fn = 0

    for pred, gt in zip(predictions, ground_truths):
        if not pred:
            regime_total += 1
            pattern_fn += len(gt.get("candle_patterns", []))
            continue

        json_valid += 1

        if pred.get("regime") == gt.get("regime"):
            regime_correct += 1
        regime_total += 1

        pred_patterns = set(p.get("name", p) if isinstance(p, dict) else str(p)
                          for p in pred.get("candle_patterns", []))
        gt_patterns = set(p.get("name", p) if isinstance(p, dict) else str(p)
                        for p in gt.get("candle_patterns", []))

        pattern_tp += len(pred_patterns & gt_patterns)
        pattern_fp += len(pred_patterns - gt_patterns)
        pattern_fn += len(gt_patterns - pred_patterns)

    precision = pattern_tp / max(pattern_tp + pattern_fp, 1)
    recall = pattern_tp / max(pattern_tp + pattern_fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)

    return {
        "json_compliance_rate": json_valid / max(total, 1),
        "regime_accuracy": regime_correct / max(regime_total, 1),
        "pattern_precision": precision,
        "pattern_recall": recall,
        "pattern_f1": f1,
        "total_samples": total,
        "json_valid_samples": json_valid,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate VLM LoRA on ChartGeometry")
    parser.add_argument("--model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--lora-path", default="outputs/vlm_lora/")
    parser.add_argument("--test-data", default="data/chart_geometry/train.jsonl")
    parser.add_argument("--output", default="outputs/vlm_lora_eval.json")
    parser.add_argument("--max-samples", type=int, default=500)
    args = parser.parse_args()

    try:
        from swift.llm import PtEngine, RequestConfig
    except ImportError:
        logger.error("ms-swift not installed. Run: pip install ms-swift[all]")
        sys.exit(1)

    logger.info(f"Loading model: {args.model} + LoRA: {args.lora_path}")
    engine = PtEngine(args.model, adapters=[args.lora_path])
    request_config = RequestConfig(max_tokens=2048, temperature=0.1)

    test_samples = []
    with open(args.test_data, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= args.max_samples:
                break
            test_samples.append(json.loads(line.strip()))

    logger.info(f"Evaluating on {len(test_samples)} samples...")

    predictions = []
    ground_truths = []

    system_prompt = (
        "You are a financial chart geometry analyst. "
        "Extract structured geometric features from the chart as JSON with fields: "
        "trend_lines, price_levels, candle_patterns, chart_formations, volume_signals, regime."
    )
    user_prompt = "Analyze this candlestick chart and extract all geometric features as structured JSON."

    for i, sample in enumerate(test_samples):
        image_path = sample.get("image_path", "")
        gt_geometry = sample.get("geometry_json", {})
        ground_truths.append(gt_geometry)

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            resp = engine.infer(
                messages=messages,
                images=[image_path] if image_path else None,
                request_config=request_config,
            )
            output_text = resp.choices[0].message.content
            parsed = parse_json_output(output_text)
            predictions.append(parsed)
        except Exception as e:
            logger.warning(f"Sample {i} inference failed: {e}")
            predictions.append({})

        if (i + 1) % 50 == 0:
            logger.info(f"  Processed {i + 1}/{len(test_samples)}")

    metrics = compute_metrics(predictions, ground_truths)
    logger.info(f"Results: {json.dumps(metrics, indent=2)}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
