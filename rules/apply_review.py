"""Apply a review file exported from the site (规则试点 → 导出评审 JSON).

  .venv/bin/python rules/apply_review.py ~/Downloads/rules_review_2026-10-23.json

Copies it to rules/_review.json (merging with what is already there), re-runs archive_rules.py so keep / archive
decisions take effect, rebuilds decisions.json and the site, and prints the 'modify' comments for the maintainer.
"""
import json, os, sys, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..'); PY = sys.executable
src = sys.argv[1]
new = json.load(open(src, encoding='utf-8'))
dst = os.path.join(HERE, '_review.json')
cur = json.load(open(dst, encoding='utf-8')) if os.path.exists(dst) else {'rules': {}}
cur['rules'].update(new.get('rules', {})); cur['imported'] = new.get('exported'); cur['source'] = os.path.basename(src)
json.dump(cur, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"merged {len(new.get('rules', {}))} reviews → {dst} ({len(cur['rules'])} total)")
for step in (['rules/archive_rules.py', '80'], ['rules/build_decisions.py'], ['site/build_site.py']):
    out = subprocess.run([PY] + [os.path.join(ROOT, step[0])] + step[1:], capture_output=True, text=True, cwd=ROOT)
    print(' ', step[0], '→', (out.stdout.strip().splitlines() or [''])[0], out.stderr.strip()[-200:])
from collections import Counter
print('decisions:', dict(Counter(x.get('decision', '') or '(comment only)' for x in cur['rules'].values())))
for rid, x in sorted(cur['rules'].items(), key=lambda kv: int(kv[0][1:])):
    if x.get('decision') == 'modify' or (x.get('comment') and x.get('decision') not in ('keep', 'archive')):
        print(f"  {rid:5} {x.get('decision', ''):8} {x.get('comment', '')[:160]}")
