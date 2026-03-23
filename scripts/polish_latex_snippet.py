"""Utility to package polished LaTeX outputs for paper writing workflow.

This script enforces the required three-part output envelope:
1) Part 1 [LaTeX]
2) Part 2 [Translation]
3) Part 3 [Modification Log]
"""

from __future__ import annotations

import argparse
from pathlib import Path


def wrap_output(polished_latex: str, translation_cn: str, log_cn: str) -> str:
    return (
        "Part 1 [LaTeX]\n"
        f"{polished_latex.strip()}\n\n"
        "Part 2 [Translation]\n"
        f"{translation_cn.strip()}\n\n"
        "Part 3 [Modification Log]\n"
        f"{log_cn.strip()}\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Format polished LaTeX snippet output")
    parser.add_argument("--latex", required=True, help="Path to polished LaTeX text")
    parser.add_argument("--translation", required=True, help="Path to Chinese literal translation")
    parser.add_argument("--log", required=True, help="Path to Chinese modification log")
    parser.add_argument("--out", default=None, help="Optional output file path")
    args = parser.parse_args()

    latex = Path(args.latex).read_text(encoding="utf-8")
    trans = Path(args.translation).read_text(encoding="utf-8")
    log = Path(args.log).read_text(encoding="utf-8")
    content = wrap_output(latex, trans, log)

    if args.out:
        Path(args.out).write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
