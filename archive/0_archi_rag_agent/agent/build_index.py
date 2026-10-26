"""Build the OpenAI embedding index over vlm_pages.sqlite.

Run once after the parser writes vlm_pages.sqlite, or whenever the source DB changes.

    python -m agent.build_index
    python -m agent.build_index --batch-size 200
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .embeddings import DEFAULT_INDEX, EMBED_MODEL, build_index
from .db import DEFAULT_DB


def main() -> None:
    p = argparse.ArgumentParser(description="Build Neufert embedding index.")
    p.add_argument("--src", type=Path, default=DEFAULT_DB, help="vlm_pages.sqlite path")
    p.add_argument("--out", type=Path, default=DEFAULT_INDEX, help="index sqlite path")
    p.add_argument("--batch-size", type=int, default=100)
    args = p.parse_args()

    n = build_index(
        src_db=args.src,
        index_db=args.out,
        batch_size=args.batch_size,
    )
    print(f"\n[done] {n} chunks indexed with {EMBED_MODEL} → {args.out}")


if __name__ == "__main__":
    main()
