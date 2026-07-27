"""One-way packaging step for the frozen KDD reproduction factor library."""
from __future__ import annotations

import argparse
import hashlib
import json
import zlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="private research JSONL")
    parser.add_argument("--output", default="src/finvl/factors/frozen_factors.bin")
    parser.add_argument("--manifest", default="configs/factor_artifact.yaml")
    args = parser.parse_args()
    records = []
    for line in Path(args.input).read_text(encoding="utf-8").splitlines():
        if line.strip() and line.strip() != "null":
            item = json.loads(line)
            if item:
                records.append(item)
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    compressed = zlib.compress(payload, level=9)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(compressed)
    digest = hashlib.sha256(compressed).hexdigest()
    manifest = Path(args.manifest)
    manifest.write_text(
        f"artifact: {output.as_posix()}\nrecords: {len(records)}\nsha256: {digest}\nformat: zlib-json-v1\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
