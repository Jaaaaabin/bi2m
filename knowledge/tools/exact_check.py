"""Strict check of every cited quote against the Neufert text in embeddings.sqlite.

exact      : quote is a verbatim substring of a content row on the cited page
ws_only    : matches only after collapsing whitespace
other_page : verbatim on another page
missing    : not found anywhere (even whitespace-collapsed)
Usage: python3 knowledge/tools/exact_check.py [--json out.json]
"""
import json, os, re, sqlite3, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
con = sqlite3.connect(os.path.join(ROOT, 'data', 'neufert', 'embeddings.sqlite'))
rows = con.execute('select page, source_table, source_row_id, content from embeddings').fetchall()
by_page = {}
for pg, tab, rid, c in rows:
    by_page.setdefault(pg, []).append((tab, rid, c))
ws = lambda s: re.sub(r'\s+', ' ', s).strip()
quotes = {}
for l in open(os.path.join(ROOT, 'knowledge', 'hard_qa.jsonl'), encoding='utf-8'):
    r = json.loads(l)
    for b in r['basis']:
        quotes.setdefault((b['page'], b['quote']), set()).add(r['hid'])
import glob
for f in glob.glob(os.path.join(ROOT, 'knowledge', 'knowledge', 'x_*.json')):   # knowledge-only citations
    for e in json.load(open(f, encoding='utf-8')):
        for pg, q in e.get('cites', []):
            quotes.setdefault((pg, q), set()).add('knowledge:' + e['title'])
res = []
for (pg, q), hids in quotes.items():
    cands = by_page.get(pg, [])
    hit = next(((t, i) for t, i, c in cands if q in c), None)
    if hit: status = 'exact'
    else:
        hit = next(((t, i) for t, i, c in cands if ws(q) in ws(c)), None)
        if hit: status = 'ws_only'
        else:
            hit = next(((t, i, p) for p, lst in by_page.items() for t, i, c in lst if q in c), None)
            status = 'other_page' if hit else 'missing'
    res.append(dict(page=pg, quote=q, status=status, source=hit, items=sorted(hids)))
import collections
print(collections.Counter(r['status'] for r in res))
if '--json' in sys.argv:
    json.dump(res, open(sys.argv[sys.argv.index('--json') + 1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for r in res:
    if r['status'] != 'exact':
        print(f"{r['status']:10s} {r['page']} | {r['quote'][:120]!r}")
