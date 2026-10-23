#!/usr/bin/env python3
"""Runs every harness in this directory against the running dev server and
summarises. Exit 1 if any script fails a check or exits non-zero.

  python3 scripts/e2e/run_all.py            # everything (perf_audit takes ~2 min)
  python3 scripts/e2e/run_all.py --quick    # skip perf_audit
  python3 scripts/e2e/run_all.py review_workflow contract   # a subset

Requirements: `pip install playwright && playwright install chromium`, and
the viewer running (`npm run dev` in Interfaces/Frontend/core).
Rules: a comparison only counts when the script reached its
assertion AND exited 0; verdict storage is restored by the scripts that
touch it, so nothing here persists review state.
"""
import os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = [
    ("contract", 300), ("foundations", 300), ("refer_zoom", 400), ("camera_panel", 300), ("views", 500),
    ("single_viewer", 200), ("sticky_headers", 300), ("review_workflow", 400),
    ("panels_default", 300), ("unload_model", 400), ("overlay_lines", 300), ("streamed_model", 300), ("streamed_refer", 400),
    ("camera_sync", 300), ("library_models", 300), ("perf_audit", 600),
]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
quick = "--quick" in sys.argv
selected = [(n, t) for n, t in ORDER if (not args or n in args) and not (quick and n == "perf_audit")]

rows, any_fail = [], False
for name, timeout in selected:
    t0 = time.time()
    try:
        proc = subprocess.run([sys.executable, os.path.join(HERE, f"{name}.py")], capture_output=True, text=True, timeout=timeout)
        out, code = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        out, code = (e.stdout or "") + (e.stderr or "") + "\nTIMEOUT", 124
    m = re.search(r"(\d+)/(\d+) checks passed", out)
    fails = len(re.findall(r"\[FAIL\]", out))
    ok = code == 0 and fails == 0 and (m is None or m.group(1) == m.group(2))
    any_fail |= not ok
    summary = f"{m.group(1)}/{m.group(2)}" if m else ("ok" if code == 0 else f"exit {code}")
    rows.append((name, "PASS" if ok else "FAIL", summary, f"{time.time() - t0:5.1f}s"))
    print(f"{'PASS' if ok else 'FAIL'}  {name:<18} {summary:>8}  {rows[-1][3]}", flush=True)
    if not ok:
        print("\n".join("      " + l for l in out.strip().splitlines()[-25:]), flush=True)

print(f"\n{sum(r[1] == 'PASS' for r in rows)}/{len(rows)} scripts passed")
sys.exit(1 if any_fail else 0)
