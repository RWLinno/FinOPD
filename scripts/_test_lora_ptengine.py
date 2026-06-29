"""Test the trained OPD LoRA via swift's PtEngine (same template as training).
This isolates whether the adapter itself is healthy, independent of the
OpenAI-API image encoding path.
"""
import os, sys, json
os.environ["IMAGE_MAX_TOKEN_NUM"] = "1024"
os.environ["CUDA_VISIBLE_DEVICES"] = os.environ.get("CUDA_VISIBLE_DEVICES", "6")

from swift import get_model_processor, get_template
from swift.infer_engine import TransformersEngine, InferRequest, RequestConfig
from peft import PeftModel

ADAPTER = "outputs/opd_lora_qwen35_v3/v0-20260618-054530/checkpoint-988"
VAL = "outputs/opd_lora_qwen35_v3/v0-20260618-054530/val_dataset.jsonl"

model, processor = get_model_processor("/Knowin/foundation/models/Qwen/Qwen3.5-9B")
model = PeftModel.from_pretrained(model, ADAPTER)
template = get_template(processor, enable_thinking=True)
engine = TransformersEngine(model, template=template)

# Load a couple of val samples
samples = []
with open(VAL) as f:
    for line in f:
        d = json.loads(line)
        msgs = [json.loads(m) if isinstance(m, str) else m for m in d["messages"]]
        imgs = [im["path"] if isinstance(im, dict) else im for im in d.get("images", [])]
        # drop assistant (we want the model to generate it)
        infer_msgs = [m for m in msgs if m["role"] != "assistant"]
        gold = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
        samples.append((infer_msgs, imgs, gold))
        if len(samples) >= 3:
            break

rc = RequestConfig(max_tokens=300, temperature=0)
for i, (msgs, imgs, gold) in enumerate(samples):
    req = InferRequest(messages=msgs, images=imgs)
    resp = engine.infer([req], rc)[0]
    out = resp.choices[0].message.content
    print(f"\n===== sample {i} =====")
    print("PRED:", repr(out[:500]))
    print("GOLD:", gold[:200])
