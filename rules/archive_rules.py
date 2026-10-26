"""Decide which rules stay active and which are archived, from the intersection of two scans over the 370 models:

  mine    rules/scan370_summary.json      per rule R:  'context'    = models where the rule's context matches (same
                                                           meaning as the colleague's 'applicable'; 'fires' would also
                                                           require the IF to be derivable, which penalises rules whose
                                                           IF the matcher cannot evaluate yet)
  theirs  neufert_applicability_*.json    per point K: 'applicable' = models where the colleague's sweep found the situation
A rule maps to its knowledge points through `from`; for a rule with several K the best K counts.

Rule:  active   if max(mine_context, theirs) >= THRESHOLD   (present in at least ~a fifth of the models by EITHER scan;
                                                          the user reviews the one-sided ones by hand)
       archived if both scans stay below the threshold
       archived otherwise. Rules without a K (R14, R44, R47) are decided on mine alone.
Nothing is deleted: rules/_status.json records status + reason, and the site shows archived rules collapsed.

.venv/bin/python rules/archive_rules.py [threshold]
"""
import json, os, sys, csv, glob
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
THRESHOLD = int(sys.argv[1]) if len(sys.argv) > 1 else 80
# manual overrides (user decision 2026-10-22): kept active although the colleague's sweep never finds the situation,
# because IFC simply lacks the attribute his sweep looks for (plot, accessibility flag) while the situation itself is common
FORCE_ACTIVE = {'R27': 'step-free access / lifts: 256 models, 201 fail — core topic T05',
                'R71': 'wheelchair turning / corridor width: 256 models — core topic T08',
                'R72': 'passing places in long corridors: 182 models — core topic T08',
                'R19': 'fire compartments ≤ 40 m: 206 models over 40 m — core topic T11',
                'R57': 'movement area beside stairs: 250 models — core topic T08',
                'R78': 'hall → kitchen / WC / stair adjacency (55 / 69): user decision 2026-10-23 — core topic T10',
                'R55': 'spiral stair as sole stair (64 / 20): user decision 2026-10-23 — core topic T01',
                'R79': 'internal corridor width 1.00 (70 / 29): user decision 2026-10-23 — core topic T10'}

RULES = {}
for fn in ('rules_pilot.jsonl', 'rules_office.jsonl', 'rules_general.jsonl'):
    for l in open(os.path.join(HERE, fn), encoding='utf-8'):
        r = json.loads(l); RULES[r['rid']] = r
mine = {s['rid']: s for s in json.load(open(os.path.join(HERE, 'scan370_summary.json'), encoding='utf-8'))['rules']}
cand = sorted(glob.glob(os.path.join(ROOT, 'neufert_applicability_*.json')))
theirs = json.load(open(cand[-1], encoding='utf-8')) if cand else None
dec = json.load(open(os.path.join(HERE, 'decisions.json'), encoding='utf-8'))
core = {r for t in dec['topics'] if t['tier'] == 'core' for r in t['rules']}

rv_path = os.path.join(HERE, '_review.json')
REVIEW = json.load(open(rv_path, encoding='utf-8'))['rules'] if os.path.exists(rv_path) else {}
status, rows = {}, []
for rid, r in RULES.items():
    mc = mine[rid]['context']; m = mc; mf = mine[rid]['fires']
    ks = [k for k in r['from'] if theirs and k in theirs['rules']]
    th = max((theirs['rules'][k]['models']['applicable'] for k in ks), default=None)
    thj = max((theirs['rules'][k]['models']['judged'] for k in ks), default=None)
    if th is None:
        keep = m >= THRESHOLD; basis = f'no K in the colleague scan; mine context={m}'
    else:
        keep = max(m, th) >= THRESHOLD; basis = f'mine context={m} (IF holds in {mf}), theirs applicable={th} (K {",".join(ks)})'
    st = 'active' if keep else 'archived'
    flag = ''
    if rid in FORCE_ACTIVE and not keep:
        st = 'active'; keep = True; basis += '; forced active by user: ' + FORCE_ACTIVE[rid]
    dec = (REVIEW.get(rid) or {}).get('decision', '')
    if dec == 'keep' and st != 'active':
        st = 'active'; basis += '; review: keep'
    elif dec == 'archive' and st != 'archived':
        st = 'archived'; basis += '; review: archive'
    if dec:
        flag = (flag + '; ' if flag else '') + f'review decision: {dec}' + ((' — ' + REVIEW[rid]['comment'][:80]) if REVIEW[rid].get('comment') else '')
    if keep and th is not None and m >= THRESHOLD and th < THRESHOLD:
        flag = f'review (one-sided): my context matches in {m} models, the colleague sweep finds it in only {th}'
    if keep and th is not None and th >= THRESHOLD and m < THRESHOLD:
        flag = f'review (one-sided): the colleague sweep finds it in {th} models, my context matches in only {m}'
    status[rid] = dict(status=st, mine_fires=mf, mine_context=mc, theirs_applicable=th, theirs_judged=thj, basis=basis, flag=flag, core=rid in core)
    rows.append(dict(rid=rid, title=r['title'], status=st, mine_fires=mf, mine_context=mc, theirs_applicable=th, theirs_judged=thj, K=','.join(r['from']), core=rid in core, flag=flag))

out = dict(threshold=THRESHOLD, criterion='max(mine_context, theirs_applicable) >= threshold; one-sided ones flagged for manual review', n_models=370, source_theirs=os.path.basename(cand[-1]) if cand else None, rules=status)
json.dump(out, open(os.path.join(HERE, '_status.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
os.makedirs(os.path.join(ROOT, 'runs', 'scan370'), exist_ok=True)
rows.sort(key=lambda x: (x['status'] != 'active', -min(x['mine_context'], x['theirs_applicable'] if x['theirs_applicable'] is not None else x['mine_context'])))
with open(os.path.join(ROOT, 'runs', 'scan370', 'rule_usage_intersection.csv'), 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
na = sum(1 for s in status.values() if s['status'] == 'active'); nr = sum(1 for s in status.values() if s['flag'])
print(f'threshold {THRESHOLD}: {na} active, {len(status) - na} archived ({nr} flagged for review) → rules/_status.json, runs/scan370/rule_usage_intersection.csv')
for x in rows:
    if x['status'] == 'archived':
        print(f"  archived {x['rid']:5} mine_ctx={x['mine_context']:3} theirs={str(x['theirs_applicable']):4} {'CORE ' if x['core'] else '     '}{x['title'][:36]}{'  ← ' + x['flag'][:40] if x['flag'] else ''}")
