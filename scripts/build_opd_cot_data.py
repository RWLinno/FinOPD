"""Augment OPD training data with explicit chain-of-thought for Qwen3.5.

Qwen3.5 is a thinking model. Training it on bare-JSON assistant turns makes it
emit an empty <think></think> and stop. We fix this at the data level by giving
each assistant turn an explicit, short reasoning trace inside <think>...</think>
followed by the JSON answer. The think content is constructed deterministically
from the structured market context already present in the user turn and the
gold label, so it is faithful (no hallucinated rationale) and cheap to build.
"""
import json
from pathlib import Path

SRC = "data/opd_train_v2/opd_multimodal_abs.jsonl"
DST = "data/opd_train_v2/opd_multimodal_cot.jsonl"


def build_think(user_text, ans):
    """Construct a concise reasoning trace from the user context + gold answer."""
    # Pull a few salient lines from the structured context
    facts = []
    for key in ["RSI(14)", "MACD", "Price vs SMA20", "Momentum(5d)", "Trend(60d)", "Regime", "Volatility"]:
        for line in user_text.splitlines():
            if key in line:
                facts.append(line.strip().rstrip(" |"))
                break
    direction = ans.get("direction", "neutral")
    action = ans.get("action", "hold")
    conf = ans.get("confidence", 0.5)
    er = ans.get("expected_return_5d", 0.0)
    reason = ans.get("reasoning", "")
    bullets = "; ".join(facts[:4])
    think = (
        f"Reading the chart and indicators: {bullets}. "
        f"{reason.capitalize() if reason else 'Weighing trend, momentum and regime'}. "
        f"This points to a {direction} 5-day outlook (expected ~{er}%), "
        f"so the action is {action} with confidence {conf}."
    )
    return think


def main():
    n, skip = 0, 0
    with open(SRC) as f, open(DST, "w") as g:
        for line in f:
            d = json.loads(line)
            msgs = d["messages"]
            user_text = msgs[1]["content"] if isinstance(msgs[1]["content"], str) else ""
            try:
                ans = json.loads(msgs[2]["content"])
            except Exception:
                skip += 1
                continue
            think = build_think(user_text, ans)
            # New assistant turn: explicit think block + clean JSON
            msgs[2]["content"] = f"<think>\n{think}\n</think>\n\n{json.dumps(ans, ensure_ascii=False)}"
            g.write(json.dumps(d, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} CoT samples ({skip} skipped) -> {DST}")


if __name__ == "__main__":
    main()
