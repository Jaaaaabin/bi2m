"""Mechanical checks for the knowledge probes (probes/probes_*.json against probes/pack_*.json).

python3 knowledge/tools/check_probes.py
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PD = os.path.join(HERE, '..', 'probes')
packs = {p['kid']: p for f in sorted(glob.glob(os.path.join(PD, 'pack_*.json'))) for p in json.load(open(f, encoding='utf-8'))}
probes = [x for f in sorted(glob.glob(os.path.join(PD, 'probes_*.json'))) for x in json.load(open(f, encoding='utf-8'))]

NUM = re.compile(r'\d+(?:[.,]\d+)?')


WORDS = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10', 'twelve': '12', 'quarter': '4', 'third': '3', 'half': '2'}


def nums(s):
    s = re.sub(r'\b(' + '|'.join(WORDS) + r')\b', lambda m: WORDS[m.group(1).lower()], s, flags=re.I)
    return {n.replace(',', '.').rstrip('0').rstrip('.') if '.' in n.replace(',', '.') else n for n in NUM.findall(s)}


problems = []
seen = set()
for p in probes:
    k = p.get('kid')
    pk = packs.get(k)
    if not pk:
        problems.append((k, 'unknown kid')); continue
    if k in seen: problems.append((k, 'duplicate kid'))
    seen.add(k)
    if p.get('title') != pk['title']: problems.append((k, f"title mismatch: {p.get('title')!r}"))
    for f in ('question', 'answer', 'mcq', 'rubric', 'basis', 'modality', 'difficulty'):
        if not p.get(f): problems.append((k, f'missing {f}'))
    src = ' '.join(e['quote'] + ' ' + e['context'] for e in pk['evidence'])
    srcn = nums(src)
    qn = nums(p.get('question', ''))
    an = nums(p.get('answer', ''))
    missing = sorted(n for n in an if n not in srcn and not (p.get('difficulty') == 'applied'))
    if missing: problems.append((k, f'answer numbers not in source: {missing}'))
    leak = sorted(n for n in an if n in qn and p.get('difficulty') != 'applied' and len(n) > 1)
    if leak: problems.append((k, f'answer number appears in question: {leak}'))
    m = p.get('mcq') or {}
    opts, ci = m.get('options', []), m.get('correct')
    if len(opts) != 4 or len(set(opts)) != 4: problems.append((k, 'mcq needs 4 distinct options'))
    elif not isinstance(ci, int) or not 0 <= ci < 4: problems.append((k, 'mcq correct index invalid'))
    else:
        if an and not (an & nums(opts[ci])): problems.append((k, f'mcq correct option shares no number with answer: {opts[ci]!r}'))
        norm = lambda t: re.sub(r'\W+', '', t.lower())
        same = [o for i, o in enumerate(opts) if i != ci and norm(o) == norm(opts[ci])]
        if same: problems.append((k, f'distractor textually identical to correct: {same}'))
    quotes = [e['quote'] for e in pk['evidence']]
    for b in p.get('basis', []):
        if not any(b in q for q in quotes): problems.append((k, f'basis not a substring of a quote: {b[:60]!r}'))
    if p.get('modality') not in ('must', 'should', 'typical'): problems.append((k, f"bad modality {p.get('modality')!r}"))
    if p.get('difficulty') not in ('recall', 'applied'): problems.append((k, f"bad difficulty {p.get('difficulty')!r}"))

missing_kids = sorted(set(packs) - seen)
print(f'{len(probes)} probes for {len(packs)} knowledge points; missing: {missing_kids}')
import collections
print('correct-option positions:', dict(collections.Counter((p.get('mcq') or {}).get('correct') for p in probes)))
print('modality:', dict(collections.Counter(p.get('modality') for p in probes)), '| difficulty:', dict(collections.Counter(p.get('difficulty') for p in probes)))
for k, msg in problems:
    print('PROBLEM', k, msg)
print('OK' if not problems and not missing_kids else f'{len(problems)} problems')
