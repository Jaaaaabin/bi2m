"""Our active rules as bi2m intent records.

For one model (bi2m content key) this reads the graph we extracted (runs/graphs/ifc4_<NNNN>.json, found through the
viewer library index data/vis_ifc4/index.json), evaluates every active rule element by element with the Facts of
rules/match_rules.py, and groups the result into one record per (rule, outcome):

    outcome   pass | fail | unknown (the IFC lacks what the requirement needs) | scenario (situation present, not judged)
    members   the target elements of that outcome (role "member") + the neighbouring elements the rule reads ("context")
    evidence  the requirement, the measured values per element, and the verbatim Neufert quote(s) with page

Records are grouped into categories by design-decision topic (rules/decisions.json), one bi2m category per topic, in
their own panel section "rules". src/recognition/zihan_rules.py registers the categories and calls records_for().

Pure Python, no ifcopenshell: runs under bi2m's env and ours.
"""
import json, os, re, statistics as st
from collections import defaultdict
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
GRAPHS = os.path.join(ROOT, 'runs', 'graphs')
LIB_INDEX = os.path.join(ROOT, 'data', 'vis_ifc4', 'index.json')
SECTION = 'rules'
OUTCOMES = ('pass', 'fail', 'unknown', 'scenario')

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location('zr_match_rules', os.path.join(HERE, 'match_rules.py'))
MR = _ilu.module_from_spec(_spec); _spec.loader.exec_module(MR)

RULES = MR.RULES
_STATUS = json.load(open(os.path.join(HERE, '_status.json'), encoding='utf-8'))['rules']
ACTIVE = sorted([r for r, x in _STATUS.items() if x['status'] == 'active'], key=lambda r: int(r[1:]))
_DEC = json.load(open(os.path.join(HERE, 'decisions.json'), encoding='utf-8'))
RULE_TOPIC = {r: t['did'] for t in _DEC['topics'] for r in t['rules']}
_IFC = {}
_p = os.path.join(HERE, 'if_concrete.jsonl')
if os.path.exists(_p):
    _IFC = {json.loads(l)['rid']: json.loads(l) for l in open(_p, encoding='utf-8')}

# one bi2m category per decision topic that has active rules, in topic order
TOPICS = []
for t in _DEC['topics']:
    if any(r in ACTIVE for r in t['rules']):
        TOPICS.append(dict(category=f"rules_{t['did'].lower()}", did=t['did'], label=f"Rules {t['did']}: {t['title_en']}",
                           level={'core': 'storey', 'secondary': 'room', 'convention': 'building'}.get(t['tier'], 'building')))
CAT_OF = {t['did']: t['category'] for t in TOPICS}


def intent_types(category):
    return [f'{category}_{o}' for o in OUTCOMES]


# ───────────────────────── graph lookup ─────────────────────────
def _name_for_key(file_key):
    if not os.path.exists(LIB_INDEX):
        return None
    idx = json.load(open(LIB_INDEX, encoding='utf-8'))
    m = idx.get('models', idx).get(file_key)
    return m['name'] if m else None


@lru_cache(maxsize=8)
def _facts(file_key):
    name = _name_for_key(file_key)
    if not name:
        return None
    gp = os.path.join(GRAPHS, 'ifc4_' + os.path.splitext(name)[0] + '.json')
    if not os.path.exists(gp):
        return None
    return MR.Facts(json.load(open(gp, encoding='utf-8')))


# ───────────────────────── helpers ─────────────────────────
def _children(F):
    ch = defaultdict(list)
    for e in F.E:
        if e['p'] == 'partOf' and e['s'] in F.N:
            ch[e['o']].append(F.N[e['s']])
    return ch


def _inside(a, b, pad=0.3):
    cx, cy = (a[0] + a[3]) / 2, (a[1] + a[4]) / 2
    return b[0] - pad <= cx <= b[3] + pad and b[1] - pad <= cy <= b[4] + pad and b[2] - 1 <= (a[2] + a[5]) / 2 <= b[5] + 1


def _depth(F, s):
    ws = [w for w in s['wins'] if w.get('size_m')]
    if ws:
        along_x = ws[0]['size_m'][0] > ws[0]['size_m'][1]
        return s['size'][1] if along_x else s['size'][0]
    if s['on_facade'] and F.ext_box:
        b = s['n']['bbox']; X = F.ext_box
        dx = min(b[0] - X[0], X[2] - b[3]); dy = min(b[1] - X[1], X[3] - b[4])
        return s['size'][1] if dx < dy else s['size'][0]
    return None


class Acc:
    """collects (outcome → targets, context, values) for one rule"""
    def __init__(self, unit=''):
        self.t = defaultdict(dict); self.c = defaultdict(dict); self.v = defaultdict(dict); self.unit = unit; self.note = {}

    def add(self, outcome, node, value=None, context=()):
        if node is None or 'id' not in node:
            return
        self.t[outcome][node['id']] = node
        if value is not None:
            self.v[outcome][node['id']] = value
        for c in context:
            if c is not None and 'id' in c and c['id'] not in self.t[outcome]:
                self.c[outcome][c['id']] = c


def _sp_ok(s, *keys):
    return any(k in s['cls'] for k in keys)


# ───────────────────────── per-rule element evaluation ─────────────────────────
def evaluate(F, rid):
    A = Acc()
    N = F.N
    if rid == 'R02':
        A.unit = 'm'
        if F.usage.startswith('office'):
            for s in F.spaces:
                if _sp_ok(s, 'office', 'meeting') and s['h']:
                    A.add('pass' if s['h'] >= 2.745 else 'fail', s['n'], round(s['h'], 2), [s['storey']])
    elif rid == 'R03':
        A.unit = 'cm (2r+t)'
        for f in F.flights:
            if f['r'] and f['t']:
                v = round(200 * f['r'] + 100 * f['t'], 1)
                A.add('pass' if 59 <= v <= 65.05 else 'fail', f['n'], v)
    elif rid == 'R04':
        A.unit = 'max risers / flight'
        ch = _children(F)
        for s in F.stairs:
            fl = [x for x in ch.get(s['id'], []) if x['type'] == 'IfcStairFlight']
            nrs = [x.get('props', {}).get('Pset_StairFlightCommon.NumberOfRiser') for x in fl]
            nrs = [x for x in nrs if isinstance(x, (int, float))]
            land = [x for x in ch.get(s['id'], []) if x['type'] == 'IfcSlab']
            if not nrs:
                A.add('unknown', s, None, fl); continue
            ok = all(3 <= n <= 18 for n in nrs) and (bool(land) or (F.storey_h_typ or 0) < 2.75)
            A.add('pass' if ok else 'fail', s, max(nrs), fl + land)
    elif rid == 'R05':
        A.unit = 'm (flight width)'
        for f in F.flights:
            if f['w']:
                A.add('pass' if f['w'] >= 0.99 else 'fail', f['n'], round(f['w'], 2))
    elif rid == 'R06':
        A.unit = 'm (railing height)'
        need = 1.0 if F.public else 0.9
        for r in F.railings:
            h = r.get('props', {}).get('Pset_RailingCommon.Height') or (r['size_m'][2] if r.get('size_m') and r['size_m'][2] < 2 else None)
            if h:
                A.add('pass' if h >= need - 0.005 else 'fail', r, round(h, 3))
    elif rid == 'R07':
        A.unit = 'm (height / width)'
        for d in F.doors:
            if not d['h']:
                continue
            ok = d['h'] >= 2.095
            if F.public and not d['ext'] and d['w'] and d['w'] > 0.5:
                ok = ok and d['w'] >= 0.885
            A.add('pass' if ok else 'fail', d['n'], f"{d['h']:.2f} / {d['w'] or 0:.2f}", d['spaces'])
    elif rid == 'R08':
        for w in F.ext_walls:
            if w['concrete']:
                A.add('pass' if w['insul'] else 'fail', w['n'], 'insulation layer' if w['insul'] else 'no insulation layer')
    elif rid == 'R09':
        A.unit = 'm²/desk'
        if F.usage.startswith('office'):
            for s in F.spaces:
                if 'office' in s['cls'] and s['furn']['desk'] and s['area']:
                    v = round(s['area'] / s['furn']['desk'], 1)
                    desks = [N[x] for x in F.contains.get(s['n']['id'], []) if x in N and 'desk' in MR.cls(MR.low(N[x]), MR.FURN)]
                    A.add('pass' if 11 <= v <= 15 else 'fail', s['n'], v, desks)
    elif rid == 'R10':
        A.unit = 'm (depth from daylight face)'
        if F.usage.startswith('office'):
            for s in F.spaces:
                if 'office' in s['cls'] and s['size']:
                    if not s['daylit']:
                        A.add('fail', s['n'], 'no daylight face'); continue
                    d = _depth(F, s)
                    A.add('pass' if (d or 0) <= 7.0 else 'fail', s['n'], round(d, 1) if d else None, s['wins'])
    elif rid == 'R11':
        if F.usage.startswith('office') and F.n_desks > 5:
            wc = F.sp('wc')
            if wc:
                for s in wc:
                    A.add('pass', s['n'], None)
            else:
                for st_ in F.storeys:
                    A.add('fail', st_, 'no WC room')
            A.note['n_desks'] = F.n_desks
    elif rid == 'R12':
        A.unit = 'm²/seat'
        for s in F.sp('meeting'):
            if s['area'] and s['furn']['chair']:
                v = round(s['area'] / s['furn']['chair'], 1)
                A.add('pass' if v >= 2.0 else 'fail', s['n'], v)
    elif rid == 'R18':
        A.unit = 'm²/workstation (building)'
        if F.usage.startswith('office') and F.n_desks and F.floor_area:
            v = round(F.floor_area / F.n_desks, 1)
            out = 'pass' if 23 <= v <= 45 else 'fail'
            for s in F.spaces:
                A.add(out, s['n'], None)
            A.note['m2_per_workstation'] = v; A.note['n_desks'] = F.n_desks
    elif rid == 'R21':
        for w in F.ext_walls:
            if w['wood'] and not (w['concrete'] or w['masonry']):
                A.add('fail', w['n'], 'timber')
            elif w['concrete'] or w['masonry']:
                A.add('pass', w['n'], 'concrete' if w['concrete'] else 'masonry')
            else:
                A.add('unknown', w['n'], 'material not named')
    elif rid == 'R23':
        if F.usage.startswith('office') and F.stairs and F.n_above >= 2:
            for s in F.stairs:
                A.add('scenario', s, None, [x['n'] for x in F.sp('stair')])
    elif rid == 'R24':
        if F.stairs and F.n_above >= 2:
            rooms = F.sp('stair')
            for s in F.stairs:
                enc = [r['n'] for r in rooms if s.get('bbox') and r['n'].get('bbox') and _inside(s['bbox'], r['n']['bbox'])]
                A.add('pass' if enc else 'fail', s, 'in stairwell' if enc else 'open (no stairwell room)', enc)
    elif rid == 'R25':
        A.unit = 'cm (riser / tread)'
        if not F.usage.startswith('residential'):
            for f in F.flights:
                if f['r'] and f['t']:
                    ok = f['r'] <= 0.1905 and f['t'] >= 0.2595 and (f['w'] or 1) >= 0.99
                    A.add('pass' if ok else 'fail', f['n'], f"{f['r'] * 100:.1f} / {f['t'] * 100:.1f}")
    elif rid == 'R30':
        if F.circulation and F.floor_area and F.floor_area / max(F.n_above, 1) >= 400:
            fr = any(w['fire'] for w in F.walls)
            for c in F.circulation:
                A.add('pass' if fr else 'unknown', c['sp']['n'], 'side walls rated' if fr else 'no FireRating on any wall')
    elif rid == 'R33':
        if F.usage.startswith('office') and F.n_desks >= 50:
            tk = F.sp('kitchen')
            for s in tk:
                A.add('pass', s['n'], round(s['area'], 1) if s['area'] else None)
            if not tk:
                for st_ in F.storeys:
                    A.add('fail', st_, 'no tea kitchen')
            A.note['n_desks'] = F.n_desks
    elif rid == 'R34':
        if F.usage.startswith('office'):
            cl = F.sp('cleaning')
            for s in cl:
                A.add('pass', s['n'], None)
            if not cl:
                for s in F.sp('storage'):
                    A.add('unknown', s['n'], 'storage, not named as cleaner\'s room')
    elif rid == 'R36':
        for s in F.spaces:
            if 'office' in s['cls'] and s['furn']['desk'] >= 4 and s['size']:
                ok = s['daylit'] and min(s['size'][:2]) <= 15
                A.add('pass' if ok else 'fail', s['n'], f"{s['furn']['desk']} desks, {'daylit' if s['daylit'] else 'no window'}")
    elif rid == 'R39':
        A.unit = 'window width / room width'
        for s in F.spaces:
            if _sp_ok(s, 'office', 'meeting') and s['wins'] and s['size']:
                ww = sum(w.get('overall_width_m') or 0 for w in s['wins'])
                d = _depth(F, s) or min(s['size'][:2])
                width = max(s['size'][:2]) if d == min(s['size'][:2]) else min(s['size'][:2])
                v = round(ww / width, 2) if width else 0
                A.add('pass' if v >= 0.65 else 'fail', s['n'], v, s['wins'])
    elif rid == 'R42':
        A.unit = 'mm (nominal width)'
        for d in F.doors:
            if d['w']:
                w = round(d['w'] * 1000)
                ok = not (w % 125 > 12 and (125 - w % 125) > 12)
                A.add('pass' if ok else 'fail', d['n'], w)
    elif rid == 'R43':
        for d in F.doors:
            if d['ext'] is True:
                bad = any(k in d['text'] for k in ('revolv', 'karussell', 'sliding', 'schiebe'))
                A.add('fail' if bad else 'pass', d['n'], 'revolving / sliding' if bad else 'swing door')
    elif rid == 'R44':
        A.unit = 'W/m²K'
        for w in F.windows:
            u = w['props'].get('Pset_WindowCommon.ThermalTransmittance')
            if isinstance(u, (int, float)) and u > 0:
                A.add('pass' if u <= 3.0 else 'fail', w['n'], round(u, 2))
            else:
                A.add('unknown', w['n'], 'no U-value')
    elif rid == 'R45':
        A.unit = '° (pitch)'
        for r in F.roofs:
            p = r.get('props', {})
            pa = p.get('Pset_RoofCommon.PitchAngle') or p.get('Pset_SlabCommon.PitchAngle')
            if isinstance(pa, (int, float)):
                A.add('pass' if pa >= 1.1 else 'fail', r, round(pa, 2))
            else:
                A.add('unknown', r, 'no pitch')
    elif rid == 'R47':
        if F.usage.startswith('office'):
            for s in F.slabs:
                A.add('scenario', s, None, F.columns)
    elif rid == 'R48':
        for s in F.slabs:
            A.add('unknown', s, 'plot area not in IFC')
    elif rid == 'R49':
        for s in F.spaces:
            A.add('pass' if s['cls'] else 'fail', s['n'], ', '.join(sorted(s['cls'])) or 'unclassified')
    elif rid == 'R50':
        for s in F.slabs:
            A.add('pass' if F.storey_h_typ else 'unknown', s, F.storey_h_typ)
    elif rid == 'R55':
        for s in F.spiral:
            ok = bool(s.get('size_m')) and max(s['size_m'][:2]) >= 1.89
            A.add('pass' if ok else 'fail', s, round(max(s['size_m'][:2]), 2) if s.get('size_m') else None)
    elif rid == 'R56':
        for s in F.stairs:
            A.add('scenario', s, None)
    elif rid == 'R57':
        if F.public:
            for s in F.stairs:
                A.add('scenario', s, None)
    elif rid == 'R58':
        if F.usage.startswith('residential') and F.n_above > 5:
            lifts = F.lifts + [x['n'] for x in F.lift_spaces] + [d for d in F.byT['IfcDoor'] if any(k in MR.low(d) for k in MR.KW['lift'])]
            if lifts:
                for l in lifts:
                    A.add('pass', l, None)
            else:
                for s in F.stairs:
                    A.add('fail', s, f'{F.n_above} storeys, no lift')
    elif rid == 'R65':
        A.unit = 'm (corridor length)'
        for c in F.circulation:
            if c['L'] and c['L'] > 30:
                ds = [d for d in F.doors if c['sp']['n']['id'] in [x['id'] for x in d['spaces']]]
                sd = [d for d in ds if d['fire'] or any(k in d['text'] for k in ('rauch', 'smoke', 'brandschutz', 'fire', 't30', 't90'))]
                A.add('pass' if sd else 'fail', c['sp']['n'], round(c['L'], 1), [d['n'] for d in ds])
    elif rid == 'R71':
        if F.public:
            for s in F.spaces:
                if s['size'] and not ({'stair', 'lift', 'storage'} & s['cls']):
                    m = min(s['size'][:2])
                    A.add('pass' if m >= 1.5 else 'fail', s['n'], round(m, 2))
    elif rid == 'R72':
        A.unit = 'm (corridor width)'
        if F.public:
            for c in F.corridors:
                if c['L'] and c['L'] > 15 and c['W']:
                    A.add('pass' if c['W'] >= 1.79 else 'fail', c['sp']['n'], round(c['W'], 2))
    elif rid == 'R83':
        A.unit = 'm³/seat'
        for s in F.sp('hall_assembly', 'meeting'):
            if s['area'] and s['h'] and s['furn']['chair']:
                v = round(s['area'] * s['h'] / s['furn']['chair'], 1)
                A.add('pass' if v >= 4 else 'fail', s['n'], v)
    elif rid == 'R87':
        if F.public:
            for c in F.circulation:
                fur = [N[x] for x in F.contains.get(c['sp']['n']['id'], []) if x in N and N[x]['type'] in ('IfcFurniture', 'IfcFurnishingElement')]
                A.add('fail' if fur else 'pass', c['sp']['n'], f'{len(fur)} furniture', fur)
    elif rid == 'R95':
        for w in F.ext_walls:
            if w['n_layers'] == 1 and w['masonry'] and not w['insul']:
                hi = any(k in w['names'] for k in ('poren', 'aerated', 'ytong', 'poroton', 'leicht', 'light', 'thermo', 'hochloch', 'dämm'))
                A.add('pass' if hi else 'unknown', w['n'], 'insulating block' if hi else 'plain masonry name')
    elif rid == 'R96':
        for w in F.ext_walls:
            layers = w['mat'].get('layers', [])
            leaves = [l for l in layers if any(k in (l.get('name') or '').lower() for k in ('ziegel', 'brick', 'mauer', 'ks', 'kalksand', 'block', 'masonry'))]
            if w['n_layers'] >= 2 and len(leaves) >= 2 and (w['air'] or w['insul']):
                air = [l for l in layers if any(k in (l.get('name') or '').lower() for k in ('air', 'luft', 'cavity'))]
                ok = all(0.04 <= (l.get('thickness_m') or 0) <= 0.15 for l in air) if air else True
                A.add('pass' if ok else 'fail', w['n'], 'cavity ok' if ok else 'air gap out of 40–150 mm')
    return A


# ───────────────────────── records ─────────────────────────
def _summary(rid, outcome, n, classes, A, values):
    r = RULES[rid]
    b = r['basis'][0] if r['basis'] else None
    vals = [v for v in values.values() if isinstance(v, (int, float))]
    rng = f"; measured {min(vals)}–{max(vals)} {A.unit}".rstrip() if vals else ''
    what = {'pass': 'meet the requirement', 'fail': 'do not meet the requirement',
            'unknown': 'cannot be judged (the IFC lacks what the requirement needs)', 'scenario': 'are in the situation this rule addresses (not judged yet)'}[outcome]
    ifs = ' AND '.join(_IFC[rid]['if_en']) if rid in _IFC else r['condition']
    note = ''.join(f'; {k} = {v}' for k, v in A.note.items())
    return (f"{rid} {r['title']}: {n} element(s) ({classes}) {what}{rng}{note}. "
            f"IF {ifs}. THEN {r['requirement']}."
            + (f" Neufert p.{b['book_page']}: “{b['quote']}”" if b else ''))


def records_for(file_key):
    """{category_id: [raw record dict]} for this model; raw records carry what make_intent needs."""
    F = _facts(file_key)
    out = defaultdict(list)
    if F is None:
        return out
    for rid in ACTIVE:
        did = RULE_TOPIC.get(rid)
        cat = CAT_OF.get(did)
        if not cat:
            continue
        try:
            A = evaluate(F, rid)
        except Exception as ex:  # one broken rule must not drop the others
            print(f'  rules: {rid} failed on {file_key}: {type(ex).__name__}: {ex}')
            continue
        r = RULES[rid]
        for outcome in OUTCOMES:
            targets = A.t.get(outcome)
            if not targets:
                continue
            guids = sorted(targets)
            ctx = {g: n for g, n in A.c.get(outcome, {}).items() if g not in targets}
            from collections import Counter
            classes = ', '.join(f'{c} {k}' for k, c in Counter(targets[g]['type'] for g in guids).most_common())
            values = {g: A.v[outcome][g] for g in guids if g in A.v[outcome]}
            nums = [v for v in values.values() if isinstance(v, (int, float))]
            label = f"{rid} {outcome}: {len(guids)} · {r['title']}" + (f" ({min(nums)}–{max(nums)})" if nums and outcome == 'fail' else '')
            out[cat].append(dict(
                intent_id=f'{file_key}-zr-{rid.lower()}-{outcome}',
                intent_type=f'{cat}_{outcome}',
                label=label,
                members=[(g, 'member', targets[g]['type']) for g in guids] + [(g, 'context', ctx[g]['type']) for g in sorted(ctx)],
                rule=rid,
                summary=_summary(rid, outcome, len(guids), classes, A, values),
                polarity='negative' if outcome == 'fail' else 'positive',
                metrics=dict(rid=rid, title=r['title'], fromK=r.get('from', []), topic=RULE_TOPIC.get(rid), outcome=outcome,
                             modality=r['modality'], requirement=r['requirement'], params=r.get('params', {}),
                             ifConditions=_IFC.get(rid, {}).get('if', []), unit=A.unit, count=len(guids),
                             contextCount=len(ctx), values=values, note=A.note,
                             basis=[{'page': b['book_page'], 'quote': b['quote']} for b in r['basis']],
                             review=(json.load(open(os.path.join(HERE, '_review.json'), encoding='utf-8'))['rules'].get(rid, {}).get('comment', '')
                                     if os.path.exists(os.path.join(HERE, '_review.json')) else '')),
            ))
    return out


if __name__ == '__main__':
    import sys
    key = sys.argv[1]
    recs = records_for(key)
    for cat, rs in recs.items():
        for x in rs:
            print(f"{cat:10} {x['intent_type']:22} {x['label'][:90]}  members={len(x['members'])}")
    print('total', sum(len(v) for v in recs.values()), 'records in', len(recs), 'categories')
