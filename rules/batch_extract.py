"""Run extract_graph.py over every IFC in a folder, in parallel. Skips graphs that already exist.

.venv/bin/python rules/batch_extract.py data/model_ifc4_0001-0370 runs/graphs --workers 6
"""
import os, sys, glob, time, subprocess, argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def one(src, dst, no_geom):
    t0 = time.time()
    cmd = [PY, os.path.join(HERE, 'extract_graph.py'), src, dst] + (['--no-geom'] if no_geom else [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return os.path.basename(src), p.returncode, round(time.time() - t0, 1), (p.stdout + p.stderr)[-400:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src_dir'); ap.add_argument('out_dir'); ap.add_argument('--workers', type=int, default=6); ap.add_argument('--no-geom', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    jobs = []
    for src in sorted(glob.glob(os.path.join(a.src_dir, '*.ifc'))):
        dst = os.path.join(a.out_dir, 'ifc4_' + os.path.splitext(os.path.basename(src))[0] + '.json')
        if not os.path.exists(dst):
            jobs.append((src, dst))
    print(f'{len(jobs)} to extract, {a.workers} workers', flush=True)
    log = open(os.path.join(a.out_dir, '_batch.log'), 'a')
    done = 0
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, s, d, a.no_geom) for s, d in jobs]
        for f in as_completed(futs):
            name, rc, secs, tail = f.result()
            done += 1
            line = f'{name} rc={rc} {secs}s' + ('' if rc == 0 else ' ERR ' + tail.replace(chr(10), ' | '))
            print(f'[{done}/{len(jobs)}] {line}', flush=True)
            log.write(line + '\n'); log.flush()


if __name__ == '__main__':
    main()
