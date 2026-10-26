"""Batch-process a directory of LOD200 case folders.

Each subfolder is expected to contain `lod200.md`. For every folder we run the
Neufert agent and write `answer.md` + figures back into the same folder.

Usage:
    python -m agent.batch /path/to/gym_envs
    python -m agent.batch /path/to/gym_envs --workers 6 --skip-existing
    python -m agent.batch /path/to/gym_envs --limit 5 --dry-run
    python -m agent.batch /path/to/gym_envs --only ac20__bathroom_wc__wc_damen__0jh6L3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .agent import run_agent


CASE_FILENAME = "lod200.md"
OUT_FILENAME = "answer.md"


def find_cases(root: Path) -> list[Path]:
    """Return subfolders that contain CASE_FILENAME."""
    cases: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("__") or child.name.startswith("."):
            continue
        if (child / CASE_FILENAME).exists():
            cases.append(child)
    return cases


def process_one(
    folder: Path,
    model: str,
    max_iters: int,
    skip_existing: bool,
) -> dict[str, Any]:
    case_md = folder / CASE_FILENAME
    answer_md = folder / OUT_FILENAME

    if skip_existing and answer_md.exists():
        return {"folder": folder.name, "status": "skipped"}

    try:
        case = case_md.read_text(encoding="utf-8")
        t0 = time.time()
        run_agent(
            case=case,
            model=model,
            max_iters=max_iters,
            verbose=False,
            output_dir=folder,
        )
        return {
            "folder": folder.name,
            "status": "ok",
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as e:
        return {
            "folder": folder.name,
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc(limit=3),
        }


def main() -> None:
    p = argparse.ArgumentParser(description="Batch Neufert agent runner.")
    p.add_argument("root", type=Path, help="folder containing case subfolders")
    p.add_argument("--model", default="gpt-5.4")
    p.add_argument("--max-iters", type=int, default=30)
    p.add_argument("--workers", type=int, default=4,
                   help="concurrent agent runs (default 4)")
    p.add_argument("--skip-existing", action="store_true",
                   help="skip folders that already have answer.md")
    p.add_argument("--dry-run", action="store_true",
                   help="list pending cases without running")
    p.add_argument("--limit", type=int, default=None,
                   help="process at most N cases (after filtering)")
    p.add_argument("--only", type=str, default=None,
                   help="process only the folder with this exact name")
    args = p.parse_args()

    if not args.root.is_dir():
        sys.exit(f"not a directory: {args.root}")

    cases = find_cases(args.root)

    if args.only:
        cases = [c for c in cases if c.name == args.only]
        if not cases:
            sys.exit(f"no case named {args.only}")

    pending = (
        [c for c in cases if not (c / OUT_FILENAME).exists()]
        if args.skip_existing
        else cases
    )
    if args.limit:
        pending = pending[: args.limit]

    print(f"found {len(cases)} cases under {args.root}, processing {len(pending)}")

    if args.dry_run:
        for c in pending[:30]:
            print(f"  {c.name}")
        if len(pending) > 30:
            print(f"  ... and {len(pending) - 30} more")
        return

    if not pending:
        print("nothing to do")
        return

    log_dir = args.root / "_batch_logs"
    log_dir.mkdir(exist_ok=True)
    ts = int(time.time())
    log_path = log_dir / f"batch_{ts}.jsonl"
    summary_path = log_dir / f"batch_{ts}.summary.txt"

    n_ok = n_err = n_skip = 0
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool, log_path.open(
        "a", encoding="utf-8"
    ) as flog:
        futures = {
            pool.submit(
                process_one, folder, args.model, args.max_iters, args.skip_existing
            ): folder
            for folder in pending
        }
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            if res["status"] == "ok":
                n_ok += 1
                tag = "OK"
            elif res["status"] == "skipped":
                n_skip += 1
                tag = "SKIP"
            else:
                n_err += 1
                tag = "ERR"

            elapsed = res.get("elapsed_s", "-")
            err = res.get("error", "")
            line = f"[{i}/{len(pending)}] {tag} {res['folder']} {elapsed}s {err}"
            print(line, flush=True)
            flog.write(json.dumps(res, ensure_ascii=False) + "\n")
            flog.flush()

    dt = time.time() - t_start
    summary = (
        f"started: {time.ctime(t_start)}\n"
        f"finished: {time.ctime()}\n"
        f"total cases pending: {len(pending)}\n"
        f"ok: {n_ok}\n"
        f"err: {n_err}\n"
        f"skipped: {n_skip}\n"
        f"wall time: {dt/60:.1f} min\n"
        f"log: {log_path}\n"
    )
    summary_path.write_text(summary, encoding="utf-8")
    print()
    print(summary)


if __name__ == "__main__":
    main()
