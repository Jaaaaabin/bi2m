"""Command-line entry point.

Usage:
    python -m agent.cli "Meeting room, 6m x 4.5m, 1 door, 2 windows, for 8 people."
    python -m agent.cli --model gpt-4o-mini --case-file case.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent import run_agent


def main() -> None:
    p = argparse.ArgumentParser(description="Neufert design-case research agent.")
    p.add_argument("case", nargs="?", help="Case description as a single string.")
    p.add_argument("--case-file", type=Path, help="Read case description from file.")
    p.add_argument("--model", default="gpt-5.4", help="OpenAI model (default: gpt-5.4).")
    p.add_argument("--max-iters", type=int, default=30)
    p.add_argument("--output-dir", type=Path, default=None,
                   help="Where to save figures + answer. Default: outputs/<slug>_<ts>/")
    p.add_argument("--quiet", action="store_true", help="Suppress tool-call logs.")
    args = p.parse_args()

    if args.case_file:
        case = args.case_file.read_text(encoding="utf-8")
    elif args.case:
        case = args.case
    else:
        print("Enter case description (Ctrl-D to submit):", file=sys.stderr)
        case = sys.stdin.read()

    if not case.strip():
        p.error("empty case")

    result = run_agent(
        case=case,
        model=args.model,
        max_iters=args.max_iters,
        verbose=not args.quiet,
        output_dir=args.output_dir,
    )
    print("\n" + "=" * 60 + "\n")
    print(result["answer"])
    print(f"\n[saved] {result['output_dir']}")


if __name__ == "__main__":
    main()
