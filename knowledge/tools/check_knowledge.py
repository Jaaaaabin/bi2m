"""Check one expansion group: items/<group>.py + knowledge/<group>.json.

python3 knowledge/tools/check_knowledge.py x_g1

- every prefix in knowledge/<group>.json matches >= 1 quote cited by items/<group>.py
- every quote cited by items/<group>.py belongs to an existing knowledge point (K list in
  knowledge_md.py) or to one of the group's new points
- every new point is used by >= 1 item of the group
- new points do not reuse prefixes of existing points
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
group = sys.argv[1]
os.environ['HARD_FILES'] = group


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


B = load('build_hard_qa', os.path.join(HERE, '..', 'build_hard_qa.py'))
KM = load('knowledge_md', os.path.join(HERE, 'knowledge_md.py'))
B.load_item_files()
items = [it for it in B.ITEMS if it.get('_src') == group]
quotes = {}
for it in items:
    for b in it['basis']:
        quotes.setdefault(b['quote'].strip(), []).append(f"{it['project']}: {it['question'][:60]}")
existing = [(t, ti, pre) for t, ti, _, pres in KM.K for pre in pres]
new = json.load(open(os.path.join(HERE, '..', 'knowledge', f'{group}.json'), encoding='utf-8'))
ok = True
for e in new:
    for k in ('topic', 'title', 'summary', 'prefixes'):
        if not e.get(k): print('MISSING', k, e.get('title')); ok = False
    for pre in e['prefixes']:
        if not any(q.startswith(pre) for q in quotes): print(f'NO QUOTE for prefix in "{e["title"]}": {pre!r}'); ok = False
        clash = [ti for _, ti, p in existing if p.startswith(pre) or pre.startswith(p)]
        if clash: print(f'OVERLAPS existing point {clash} with prefix {pre!r}'); ok = False
for q, uses in quotes.items():
    hit_new = [e['title'] for e in new if any(q.startswith(p) for p in e['prefixes'])]
    hit_old = [ti for _, ti, p in existing if q.startswith(p)]
    if len(hit_new) + len(set(hit_old)) == 0: print(f'UNASSIGNED quote: {q[:90]!r}'); ok = False
    if len(hit_new) + len(set(hit_old)) > 1: print(f'AMBIGUOUS quote {q[:60]!r}: {hit_new + hit_old}'); ok = False
print(f'{group}: {len(items)} items, {len(new)} new knowledge points, {len(quotes)} distinct quotes ->', 'OK' if ok else 'FIX ABOVE')
sys.exit(0 if ok else 1)
