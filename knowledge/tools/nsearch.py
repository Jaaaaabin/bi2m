"""grep the parsed Neufert: python3 nsearch.py REGEX [CHAPTER_REGEX] [CONTEXT_CHARS]"""
import json, re, sys, os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
R = os.path.join(_ROOT, 'data', 'neufert', 'dataset')
P = [json.loads(l) for l in open(os.path.join(R, 'pages.jsonl'), encoding='utf-8')]
cap = {}
for l in open(os.path.join(R, 'index.jsonl'), encoding='utf-8'):
    x = json.loads(l)
    for c in (x.get('captions') or []) + ([x['caption']] if x.get('caption') else []):
        t = c if isinstance(c, str) else (c.get('text') if isinstance(c, dict) else None)
        if t: cap.setdefault(x['page'], []).append(t)
pat = re.compile(sys.argv[1], re.I); chap = sys.argv[2] if len(sys.argv) > 2 else ''; W = int(sys.argv[3]) if len(sys.argv) > 3 else 260
n = 0
for p in P:
    if chap and not re.search(chap, p['chapter'] or '', re.I): continue
    seen = set()
    for uid, t in [(b['id'], b['text']) for b in p['body_text']] + [(f"{p['page']}_cap", c) for c in cap.get(p['page'], [])]:
        m = pat.search(t)
        if not m or t in seen: continue
        seen.add(t); s = max(0, m.start() - W); e = min(len(t), m.end() + W)
        print(f"[p.{p['book_page']} {p['chapter']} | {uid}] …{t[s:e]}…".replace('\n', ' ')); n += 1
print('hits', n)
