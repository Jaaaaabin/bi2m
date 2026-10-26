"""Match the 103 rules against every graph in runs/graphs/ and rank the rules by how often they apply.

For each (model, rule) it records
  context    True if the rule's context (entity + match preconditions) has a non-empty match in the graph
  condition  True / False if the IF part can be evaluated, None if the graph lacks what it needs
  verdict    pass / fail / mixed / unknown when the THEN part can be checked mechanically, None otherwise
  note       the numbers behind it
Only the parts that are machine-checkable from the graph are evaluated; everything that needs the model card
(usage, headcount, plot) is inferred from room names where possible and reported as such.

.venv/bin/python rules/match_rules.py            # all graphs → runs/scan370/matches.jsonl + summary.md/.csv + rules/scan370_summary.json
.venv/bin/python rules/match_rules.py ifc4_0204  # one model, print its row
"""
import json, os, sys, glob, re, math, collections, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
GRAPHS = os.path.join(ROOT, 'runs', 'graphs')
OUTDIR = os.path.join(ROOT, 'runs', 'scan370')

RULES = {}
for fn in ('rules_pilot.jsonl', 'rules_office.jsonl', 'rules_general.jsonl'):
    for l in open(os.path.join(HERE, fn), encoding='utf-8'):
        r = json.loads(l); RULES[r['rid']] = r

# ───────────────────────── room / furniture classification (en + de) ─────────────────────────
KW = {
    'office': ['office', 'büro', 'buero', 'open-plan', 'openplan', 'workspace', 'working space', 'work space', 'workplace', 'arbeitsraum', 'co-work', 'cowork', 'desk area', 'cubicle'],
    'meeting': ['meeting', 'conference', 'besprech', 'konferenz', 'boardroom', 'sitzung'],
    'wc': ['wc', 'toilet', 'toilette', 'bathroom', 'bad', 'restroom', 'sanitär', 'sanitary', 'lavatory', 'washroom', 'shower', 'dusche', 'badezimmer'],
    'kitchen': ['kitchen', 'küche', 'kueche', 'tea', 'pantry', 'kitchenette', 'teeküche'],
    'corridor': ['corridor', 'flur', 'hallway', 'gang', 'passage', 'korridor', 'circulation', 'hall', 'lobby', 'foyer', 'diele', 'entrance', 'eingang', 'vestibule', 'atrium'],
    'stair': ['stair', 'treppe', 'staircase', 'stairwell', 'treppenhaus'],
    'lift': ['lift', 'elevator', 'aufzug', 'fahrstuhl'],
    'storage': ['storage', 'store', 'lager', 'abstell', 'archiv', 'archive', 'closet', 'utility', 'technik', 'plant', 'mechanical', 'hausanschluss', 'server', 'it room', 'edv', 'shaft', 'schacht', 'cleaning', 'putz', 'janitor'],
    'living': ['living', 'wohn', 'lounge', 'family room', 'dining', 'ess', 'wohnzimmer'],
    'bed': ['bed', 'schlaf', 'kinder', 'child', 'master', 'guest room', 'gästezimmer', 'dorm', 'bedroom'],
    'balcony': ['balcon', 'balkon', 'loggia', 'terrace', 'terrasse', 'patio', 'veranda'],
    'garage': ['garage', 'parking', 'park', 'carport', 'stellplatz', 'tiefgarage'],
    'edu': ['class', 'klasse', 'seminar', 'lecture', 'hörsaal', 'hoersaal', 'school', 'schule', 'teaching', 'lab', 'labor', 'library', 'bibliothek', 'auditorium', 'unterricht'],
    'health': ['patient', 'ward', 'treatment', 'behandl', 'exam', 'untersuch', 'clinic', 'praxis', 'therapy', 'nurse', 'operating', 'op-'],
    'hotel': ['hotel', 'reception', 'rezeption', 'suite'],
    'shop': ['shop', 'retail', 'store front', 'laden', 'verkauf', 'market', 'supermarkt', 'café', 'cafe', 'restaurant', 'bar', 'canteen', 'kantine', 'mensa', 'cafeteria', 'gastro'],
    'sport': ['gym', 'sport', 'fitness', 'halle', 'pool', 'schwimm'],
    'mail': ['mail', 'post'],
    'server': ['server', 'edv', 'it room', 'data', 'rechenzentrum'],
    'archive': ['archiv', 'archive', 'registratur', 'records'],
    'cleaning': ['cleaning', 'putz', 'janitor', 'reinigung'],
    'entrance_hall': ['entrance', 'eingang', 'foyer', 'lobby', 'diele', 'windfang', 'vestibule', 'empfang', 'reception'],
    'hall_assembly': ['auditorium', 'hörsaal', 'hoersaal', 'lecture', 'aula', 'assembly', 'theatre', 'theater', 'cinema', 'concert', 'saal', 'veranstaltung'],
    'seminar': ['seminar'],
}
FURN = {
    'desk': ['desk', 'schreibtisch', 'workstation', 'arbeitsplatz', 'work station'],
    'chair': ['chair', 'stuhl', 'sessel', 'seat', 'hocker', 'bench'],
    'bed': ['bed', 'bett'],
    'wc': ['toilet', 'wc', 'toilette', 'closet', 'urinal'],
    'basin': ['basin', 'sink', 'waschbecken', 'waschtisch', 'lavatory', 'washbasin'],
    'bath': ['bath', 'badewanne', 'tub'],
    'shower': ['shower', 'dusche'],
    'cook': ['cook', 'herd', 'stove', 'oven', 'range', 'kitchen', 'küche', 'refrigerator', 'kühlschrank', 'fridge', 'dishwasher'],
    'sofa': ['sofa', 'couch', 'lounge', 'armchair'],
    'table': ['table', 'tisch'],
}


def low(n):
    return ((n.get('name') or '') + ' ' + (n.get('long_name') or '') + ' ' + (n.get('type_name') or '')).lower()


def cls(text, table):
    out = set()
    for k, kws in table.items():
        if any(w in text for w in kws):
            out.add(k)
    if table is FURN and 'chair' in out:
        out.discard('desk'); out.discard('table')   # "Chair - Desk (4)", "Table-chair-combination" are seats, not work surfaces
    if table is KW and 'office' in out and ('outer office' in text or 'vorzimmer' in text):
        pass
    return out


CORR_STRICT = ['corridor', 'flur', 'hallway', 'gang', 'korridor', 'passage']


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


# ───────────────────────── facts from a graph ─────────────────────────
class Facts:
    def __init__(self, G):
        self.G = G
        self.model = G['model'] if not G['model'].startswith('ifc4_') else G['model']
        if not self.model.startswith('ifc4_') and re.fullmatch(r'\d{4}', self.model):
            self.model = 'ifc4_' + self.model
        self.N = {n['id']: n for n in G['nodes']}
        self.E = G['edges']
        self.byT = collections.defaultdict(list)
        for n in self.N.values():
            self.byT[n['type']].append(n)
        self.has_geom = any(n.get('bbox') for n in self.N.values())
        self.parent = {}
        for e in self.E:
            if e['p'] in ('partOf', 'containedIn'):
                self.parent.setdefault(e['s'], e['o'])
        self.contains = collections.defaultdict(list)
        self.opens = collections.defaultdict(list)
        self.serves = collections.defaultdict(set)
        for e in self.E:
            if e['p'] == 'contains':
                self.contains[e['s']].append(e['o'])
            elif e['p'] == 'opensTo':
                self.opens[e['o']].append(e['s'])
            elif e['p'] == 'serves':
                self.serves[e['s']].add(e['o'])
        # storeys
        self.storeys = sorted([n for n in self.byT['IfcBuildingStorey'] if num(n.get('elevation_m')) is not None], key=lambda s: s['elevation_m'])
        el = [s['elevation_m'] for s in self.storeys]
        # collapse duplicate elevations (Revit exports levels for everything)
        el_u = []
        for v in el:
            if not el_u or v - el_u[-1] > 0.5:
                el_u.append(v)
        self.elevs = el_u
        self.n_storeys = len(el_u)
        self.n_above = sum(1 for v in el_u if v > -0.5)
        self.storey_h = [round(b - a, 2) for a, b in zip(el_u, el_u[1:])]
        self.storey_h_typ = st.median(self.storey_h) if self.storey_h else None
        # storey of a node
        self.storey_of = {}
        sid = {s['id'] for s in self.storeys}
        for n in self.N.values():
            p = self.parent.get(n['id'])
            hops = 0
            while p and p not in sid and hops < 4:
                p = self.parent.get(p); hops += 1
            if p in sid:
                self.storey_of[n['id']] = self.N[p]
        # occupied storeys: those with spaces or doors or furniture
        occ = set()
        for n in self.N.values():
            if n['type'] in ('IfcSpace', 'IfcDoor', 'IfcFurniture', 'IfcFurnishingElement') and n['id'] in self.storey_of:
                occ.add(self.storey_of[n['id']]['elevation_m'])
        self.H_top = max(occ) if occ else (el_u[-1] if el_u else None)
        self.H_top_src = 'occupied storey' if occ else 'top storey'
        # building extent (from walls / slabs), used for "is this room on the façade"
        bbs = [n['bbox'] for n in self.walls_nodes() if n.get('bbox')]
        self.extent = None; self.ext_box = None
        if bbs:
            self.ext_box = [min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[3] for b in bbs), max(b[4] for b in bbs)]
            self.extent = [round(self.ext_box[2] - self.ext_box[0], 1), round(self.ext_box[3] - self.ext_box[1], 1)]
        # spaces
        self.spaces = []
        for s in self.byT['IfcSpace']:
            t = low(s); c = cls(t, KW)
            p = s.get('props', {})
            area = num(p.get('Qto_SpaceBaseQuantities.NetFloorArea')) or num(p.get('Qto_SpaceBaseQuantities.GrossFloorArea'))
            area_src = 'qto' if area else None
            if not area and s.get('size_m'):
                area = round(s['size_m'][0] * s['size_m'][1], 1); area_src = 'bbox'
            h = num(p.get('Qto_SpaceBaseQuantities.Height')) or (s['size_m'][2] if s.get('size_m') else None)
            h_src = 'qto' if num(p.get('Qto_SpaceBaseQuantities.Height')) else ('bbox' if h else None)
            furn = [self.N[x] for x in self.contains.get(s['id'], []) if x in self.N]
            fc = collections.Counter()
            for f in furn:
                for k in cls(low(f), FURN):
                    fc[k] += 1
            wins = [self.N[w] for w in self.opens.get(s['id'], []) if self.N[w]['type'] == 'IfcWindow']
            doors = [self.N[w] for w in self.opens.get(s['id'], []) if self.N[w]['type'] == 'IfcDoor']
            on_facade = None
            if s.get('bbox') and self.ext_box:
                b = s['bbox']; X = self.ext_box
                on_facade = (b[0] - X[0] < 0.8) or (X[2] - b[3] < 0.8) or (b[1] - X[1] < 0.8) or (X[3] - b[4] < 0.8)
            self.spaces.append(dict(n=s, cls=c, text=t, area=area, area_src=area_src, h=h, h_src=h_src, furn=fc, n_furn=len(furn), wins=wins, doors=doors,
                                    size=s.get('size_m'), storey=self.storey_of.get(s['id']), on_facade=on_facade, daylit=bool(wins) or bool(on_facade)))
        self.n_spaces = len(self.spaces)
        cnt = collections.Counter()
        for sp in self.spaces:
            for k in sp['cls']:
                cnt[k] += 1
        self.space_cls = cnt
        # usage
        res = cnt['living'] + cnt['bed'] + cnt['balcony']
        off = cnt['office'] + cnt['meeting']
        edu = cnt['edu']; hea = cnt['health']; hot = cnt['hotel']; shop = cnt['shop']
        scores = {'residential': res, 'office': off, 'education': edu, 'health': hea, 'hotel': hot, 'retail/gastro': shop}
        best = max(scores, key=scores.get)
        self.usage = best if scores[best] >= 2 else 'unknown'
        self.usage_scores = scores
        self.furn_all = collections.Counter()
        for n in self.byT['IfcFurniture'] + self.byT['IfcFurnishingElement']:
            for k in cls(low(n), FURN):
                self.furn_all[k] += 1
        self.n_desks = self.furn_all['desk']
        self.n_beds = self.furn_all['bed']
        if self.usage == 'unknown' and self.n_beds >= 2 and self.n_desks < self.n_beds:
            self.usage = 'residential?'
        if self.usage == 'unknown' and self.n_desks >= 5:
            self.usage = 'office?'
        self.public = self.usage in ('office', 'office?', 'education', 'health', 'hotel', 'retail/gastro')
        # stairs
        self.flights = []
        for fl in self.byT['IfcStairFlight']:
            p = fl.get('props', {})
            r = num(p.get('Pset_StairFlightCommon.RiserHeight')); t = num(p.get('Pset_StairFlightCommon.TreadLength')); nr = num(p.get('Pset_StairFlightCommon.NumberOfRiser'))
            w = None
            if fl.get('size_m'):
                w = min(fl['size_m'][0], fl['size_m'][1])
            self.flights.append(dict(n=fl, r=r, t=t, nr=nr, w=w))
        self.stairs = self.byT['IfcStair']
        self.landings = [s for s in self.byT['IfcSlab'] if (s.get('predefined_type') == 'LANDING' or 'landing' in low(s) or 'podest' in low(s))]
        self.railings = self.byT['IfcRailing']
        self.rail_h = [num(r.get('props', {}).get('Pset_RailingCommon.Height')) for r in self.railings]
        self.rail_h = [h for h in self.rail_h if h]
        if not self.rail_h:
            self.rail_h = [r['size_m'][2] for r in self.railings if r.get('size_m') and r['size_m'][2] < 2.0]
        self.spiral = [s for s in self.stairs if (s.get('predefined_type') or '') == 'SPIRAL_STAIR' or 'spiral' in low(s) or 'spindel' in low(s) or 'wendel' in low(s)]
        # lifts
        self.lifts = list(self.byT['IfcTransportElement'])
        self.lift_spaces = [sp for sp in self.spaces if 'lift' in sp['cls']]
        self.lift_doors = [d for d in self.byT['IfcDoor'] if any(k in low(d) for k in KW['lift'])]
        self.has_lift = bool(self.lifts or self.lift_spaces or self.lift_doors)
        self.lift_src = 'IfcTransportElement' if self.lifts else ('space name' if self.lift_spaces else ('door name' if self.lift_doors else None))
        self.ramps = self.byT['IfcRamp'] + self.byT['IfcRampFlight']
        # doors / windows
        self.doors = []
        for d in self.byT['IfcDoor']:
            p = d.get('props', {})
            self.doors.append(dict(n=d, w=num(d.get('overall_width_m')), h=num(d.get('overall_height_m')), ext=p.get('Pset_DoorCommon.IsExternal'),
                                   fire=p.get('Pset_DoorCommon.FireRating'), text=low(d), spaces=[self.N[x] for x in self.opens_rev(d['id'])]))
        self.windows = []
        for w in self.byT['IfcWindow']:
            sill = None
            if w.get('bbox') and w['id'] in self.storey_of:
                sill = round(w['bbox'][2] - self.storey_of[w['id']]['elevation_m'], 2)
            self.windows.append(dict(n=w, w=num(w.get('overall_width_m')), h=num(w.get('overall_height_m')), sill=sill, text=low(w),
                                     props=w.get('props', {}), op=(w.get('operation_type') or '')))
        # walls
        self.walls = []
        for w in self.byT['IfcWall'] + self.byT['IfcWallStandardCase']:
            p = w.get('props', {}); m = w.get('material') or {}
            names = ' '.join((l.get('name') or '') for l in m.get('layers', [])).lower() + ' ' + low(w)
            thick = m.get('total_m')
            if not thick and w.get('size_m') and min(w['size_m'][:2]) < 0.8:
                thick = round(min(w['size_m'][:2]), 3)
            self.walls.append(dict(n=w, ext=p.get('Pset_WallCommon.IsExternal'), lb=p.get('Pset_WallCommon.LoadBearing'), fire=p.get('Pset_WallCommon.FireRating'),
                                   u=num(p.get('Pset_WallCommon.ThermalTransmittance')), mat=m, names=names,
                                   n_layers=len(m.get('layers', [])), total=thick,
                                   insul=any(k in names for k in ['dämm', 'daemm', 'insul', 'wärme', 'waerme', 'eps', 'xps', 'mineral', 'mw ', 'rockwool', 'glaswolle', 'steinwolle', 'wdvs', 'etics', 'polystyr', 'pur ', 'pir ']),
                                   concrete=any(k in names for k in ['beton', 'concrete', 'stb', 'stahlbeton', 'c20', 'c25', 'c30']),
                                   masonry=any(k in names for k in ['ziegel', 'brick', 'mauer', 'mw', 'masonry', 'kalksand', 'ks ', 'poroton', 'block', 'porenbeton', 'ytong', 'aerated', 'cmu']),
                                   air=any(k in names for k in ['air', 'luft', 'cavity', 'hinterlüft', 'ventilat']),
                                   glass=any(k in names for k in ['glas', 'glass']),
                                   wood=any(k in names for k in ['holz', 'wood', 'timber', 'clt', 'osb'])))
        self.ext_walls = [w for w in self.walls if w['ext'] is True]
        self.curtain = self.byT['IfcCurtainWall']
        self.roofs = self.byT['IfcRoof'] + [s for s in self.byT['IfcSlab'] if (s.get('predefined_type') == 'ROOF' or 'roof' in low(s) or 'dach' in low(s))]
        self.roof_pitch = []
        for r in self.roofs:
            p = r.get('props', {})
            pa = num(p.get('Pset_RoofCommon.PitchAngle')) or num(p.get('Pset_SlabCommon.PitchAngle'))
            if pa is not None:
                self.roof_pitch.append(pa)
        self.roof_names = ' '.join(low(r) + ' ' + ' '.join((l.get('name') or '') for l in (r.get('material') or {}).get('layers', [])) for r in self.roofs).lower()
        self.grids = self.byT['IfcGrid']
        self.zones = self.byT['IfcZone']
        self.sanitary = self.byT['IfcSanitaryTerminal']
        self.columns = self.byT['IfcColumn']
        self.slabs = [s for s in self.byT['IfcSlab'] if s.get('predefined_type') not in ('LANDING',)]
        self.floor_area = sum((sp['area'] or 0) for sp in self.spaces)
        # corridors (strict: named corridor / long and thin with ≥ 3 doors) vs circulation (also halls, lobbies, foyers)
        self.corridors, self.circulation = [], []
        for sp in self.spaces:
            L = max(sp['size'][:2]) if sp['size'] else None
            W = min(sp['size'][:2]) if sp['size'] else None
            strict = any(k in sp['text'] for k in CORR_STRICT) or (L and W and W > 0 and L / W > 2.5 and len(sp['doors']) >= 3)
            if strict:
                self.corridors.append(dict(sp=sp, L=L, W=W))
            if strict or 'corridor' in sp['cls']:
                self.circulation.append(dict(sp=sp, L=L, W=W))

    def walls_nodes(self):
        return self.byT['IfcWall'] + self.byT['IfcWallStandardCase'] + self.byT['IfcCurtainWall'] + self.byT['IfcSlab']

    def opens_rev(self, did):
        return [e['o'] for e in self.E if e['p'] == 'opensTo' and e['s'] == did] if False else self._opens_rev().get(did, [])

    def _opens_rev(self):
        if not hasattr(self, '_or'):
            self._or = collections.defaultdict(list)
            for e in self.E:
                if e['p'] == 'opensTo':
                    self._or[e['s']].append(e['o'])
        return self._or

    def sp(self, *keys):
        return [s for s in self.spaces if any(k in s['cls'] for k in keys)]


# ───────────────────────── rule evaluators ─────────────────────────
def R(ctx, cond=None, verdict=None, **note):
    return dict(context=bool(ctx), condition=cond, verdict=verdict, note=note)


def pf(ok):
    return 'pass' if ok else 'fail'


def ev_R01(F):
    if F.H_top is None: return R(False)
    hr = F.H_top > 22
    return R(True, hr, 'fail' if hr and len(F.stairs) < 2 else ('pass' if hr else None), H_top=F.H_top, src=F.H_top_src)


def high_rise(F):
    return F.H_top is not None and F.H_top > 22


def ev_R02(F):
    sp = [s for s in F.spaces if F.usage.startswith('office') and ('office' in s['cls'] or 'meeting' in s['cls']) and s['h']]
    if not F.usage.startswith('office') or not sp: return R(False, note_usage=F.usage)
    hs = [s['h'] for s in sp]
    return R(True, True, pf(min(hs) >= 2.75 - 0.01), h_min=round(min(hs), 2), h_med=round(st.median(hs), 2), src=sp[0]['h_src'], n=len(hs))


def ev_R03(F):
    fl = [f for f in F.flights if f['r'] and f['t']]
    if not fl: return R(bool(F.stairs))
    v = [2 * f['r'] * 100 + f['t'] * 100 for f in fl]
    return R(True, True, pf(all(59 <= x <= 65.05 for x in v)), two_r_plus_t=[round(min(v), 1), round(max(v), 1)], n=len(fl))


def ev_R04(F):
    if not F.flights or F.storey_h_typ is None: return R(bool(F.stairs))
    met = F.storey_h_typ >= 2.75
    nrs = [f['nr'] for f in F.flights if f['nr']]
    if not nrs: return R(True, met, None, storey_h=F.storey_h_typ)
    ok = all(3 <= n <= 18 for n in nrs) and (bool(F.landings) or max(nrs) <= 18)
    return R(True, met, pf(ok) if met else None, storey_h=F.storey_h_typ, n_riser_max=max(nrs), landings=len(F.landings))


def ev_R05(F):
    fl = [f for f in F.flights if f['w']]
    if not F.stairs: return R(False)
    if not fl: return R(True, True, None)
    wmin = min(f['w'] for f in fl)
    return R(True, True, pf(wmin >= 0.99), w_min=round(wmin, 2), n_stair=len(F.stairs))


def ev_R06(F):
    if not F.railings: return R(False)
    if not F.rail_h: return R(True, True, None)
    hmin = min(F.rail_h)
    need = 1.0 if F.public else 0.9
    return R(True, True, pf(hmin >= need - 0.005), h_min=round(hmin, 2), need=need)


def ev_R07(F):
    ds = [d for d in F.doors if d['h']]
    if not ds: return R(False)
    hmin = min(d['h'] for d in ds)
    ok = hmin >= 2.095
    if F.public:
        ws = [d['w'] for d in F.doors if d['w'] and not d['ext'] and d['w'] > 0.5]
        narrow = sum(1 for w in ws if w < 0.885)
        ok = ok and narrow == 0
        return R(True, True, pf(ok), h_min=round(hmin, 2), n_doors_under_0_9=narrow, n_doors=len(ws), public=True)
    return R(True, True, pf(ok), h_min=round(hmin, 2))


def ev_R08(F):
    cw = [w for w in F.ext_walls if w['concrete']]
    if not cw: return R(False, n_ext=len(F.ext_walls))
    ins = [w for w in cw if w['insul']]
    return R(True, True, pf(len(ins) == len(cw)) if len(ins) in (0, len(cw)) else 'mixed', n_concrete_ext=len(cw), n_with_insulation=len(ins))


def ev_R09(F):
    sp = [s for s in F.spaces if ('office' in s['cls']) and s['furn']['desk'] and s['area']]
    if not F.usage.startswith('office') or not sp: return R(F.usage.startswith('office') and F.n_desks > 0)
    per = [s['area'] / s['furn']['desk'] for s in sp]
    med = st.median(per)
    return R(True, True, 'pass' if 11 <= med <= 15 else ('mixed' if 8 <= med <= 20 else 'fail'), m2_per_desk_median=round(med, 1), n_rooms=len(sp), src=sp[0]['area_src'])


def ev_R10(F):
    if not F.usage.startswith('office'): return R(False)
    sp = [s for s in F.spaces if 'office' in s['cls'] and s['size']]
    if not sp: return R(True, True, None)
    nowin = [s for s in sp if not s['daylit']]
    def depth(s):
        # depth = room extent perpendicular to the daylight face: the window's long axis tells which wall carries it
        ws = [w for w in s['wins'] if w.get('size_m')]
        if ws:
            along_x = ws[0]['size_m'][0] > ws[0]['size_m'][1]
            return s['size'][1] if along_x else s['size'][0]
        if s['on_facade'] and F.ext_box:
            b = s['n']['bbox']; X = F.ext_box
            dx = min(b[0] - X[0], X[2] - b[3]); dy = min(b[1] - X[1], X[3] - b[4])
            return s['size'][1] if dx < dy else s['size'][0]   # façade is the x-side → depth runs in y
        return None
    deep = [s for s in sp if s['daylit'] and (depth(s) or 0) > 7.0]
    return R(True, True, pf(not nowin and not deep) if F.has_geom else None, n_office=len(sp), n_without_daylight_face=len(nowin), n_deeper_than_7m=len(deep),
             depth_max=round(max((depth(s) or 0) for s in sp), 1))


def ev_R11(F):
    if not F.usage.startswith('office'): return R(False)
    wc = F.sp('wc')
    return R(True, F.n_desks > 5, pf(bool(wc)) if F.n_desks > 5 else None, n_desks=F.n_desks, n_wc_rooms=len(wc))


def ev_R12(F):
    sp = [s for s in F.sp('meeting') if s['area'] and s['furn']['chair']]
    if not F.sp('meeting'): return R(False)
    if not sp: return R(True, True, None)
    per = [s['area'] / s['furn']['chair'] for s in sp]
    return R(True, True, pf(st.median(per) >= 2.0), m2_per_seat_median=round(st.median(per), 1), n=len(sp))


def ev_R13(F):
    return R(bool(F.ext_walls), True, 'unknown', note='no plot boundary in IFC')


def ev_R14(F):
    if not F.usage.startswith('office'): return R(False)
    return R(True, None, None, note='needs TrueNorth + window orientation (not in graph yet)')


def ev_R15(F):
    return R(F.usage.startswith('office') and F.n_spaces > 5, True, None)


def ev_R16(F):
    return R(F.usage.startswith('office') and (bool(F.grids) or bool(F.windows)), True, None, grids=len(F.grids))


def ev_R17(F):
    if not F.usage.startswith('office') or not F.corridors: return R(False)
    if not F.extent: return R(True, True, None)
    d = min(F.extent)
    return R(True, True, 'pass' if 11 <= d <= 14 else 'fail', depth_m=d)


def ev_R18(F):
    if not F.usage.startswith('office') or not F.n_desks or not F.floor_area: return R(F.usage.startswith('office') and F.n_desks > 0)
    per = F.floor_area / F.n_desks
    return R(True, True, 'pass' if 23 <= per <= 45 else 'fail', m2_per_ws=round(per, 1), n_desks=F.n_desks)


def ev_R19(F):
    if not F.extent: return R(bool(F.ext_walls), None, None)
    L = max(F.extent)
    fw = [w for w in F.walls if w['fire'] and re.search(r'9\d|F ?90|REI ?90|F ?120', str(w['fire']))]
    return R(True, L > 40, (pf(bool(fw)) if fw else 'unknown') if L > 40 else None, L_m=L, n_f90_walls=len(fw))


def ev_R20(F):
    lb = [w for w in F.walls if w['lb'] is True] + F.columns
    if not lb: return R(False)
    fr = [w for w in F.walls if w['lb'] is True and w['fire']]
    return R(True, True, 'unknown' if not fr else 'pass', n_loadbearing=len(lb), n_with_fire_rating=len(fr))


def ev_R21(F):
    if not F.ext_walls: return R(False)
    comb = [w for w in F.ext_walls if w['wood'] and not (w['concrete'] or w['masonry'])]
    known = [w for w in F.ext_walls if w['concrete'] or w['masonry'] or w['wood']]
    if not known: return R(True, True, 'unknown', n_ext=len(F.ext_walls))
    return R(True, True, pf(not comb), n_ext=len(F.ext_walls), n_timber_ext=len(comb))


def ev_R22(F):
    if F.n_above < 2: return R(False, n_storeys=F.n_above)
    return R(True, True, pf(len(F.stairs) >= 2), n_stairs=len(F.stairs), n_storeys=F.n_above)


def ev_R23(F):
    if not F.usage.startswith('office') or not F.stairs or F.n_above < 2: return R(False)
    return R(True, True, None, n_stairs=len(F.stairs), note='walking distance needs path geometry')


def ev_R24(F):
    if not F.stairs or F.n_above < 2: return R(False)
    ss = F.sp('stair')
    return R(True, True, pf(len(ss) >= len(F.stairs) / 2) if F.spaces else None, n_stairs=len(F.stairs), n_stair_rooms=len(ss))


def ev_R25(F):
    fl = [f for f in F.flights if f['r'] and f['t']]
    if F.usage.startswith('residential') or not F.stairs: return R(False)
    if not fl: return R(True, True, None)
    ok = all(f['r'] <= 0.1905 and f['t'] >= 0.2595 for f in fl)
    wok = all((f['w'] or 1) >= 0.99 for f in fl)
    return R(True, True, pf(ok and wok), r_max_cm=round(max(f['r'] for f in fl) * 100, 1), t_min_cm=round(min(f['t'] for f in fl) * 100, 1))


def ev_R26(F):
    return R(F.usage.startswith('office') and bool(F.stairs), True, None)


def ev_R27(F):
    if not F.public: return R(False)
    if F.n_above <= 1: return R(True, True, 'pass', note='single storey')
    return R(True, True, pf(F.has_lift or bool(F.ramps)), has_lift=F.has_lift, lift_src=F.lift_src, n_storeys=F.n_above)


def ev_R28(F):
    if not F.has_lift: return R(False)
    L = [l for l in F.lifts if l.get('size_m')]
    if not L: return R(True, True, None, lift_src=F.lift_src)
    ok = all(sorted(l['size_m'][:2])[0] >= 1.09 and sorted(l['size_m'][:2])[1] >= 1.39 for l in L)
    return R(True, True, pf(ok), n=len(L), car=L[0]['size_m'][:2])


def ev_R29(F):
    if not F.ramps: return R(False)
    return R(True, True, None, n_ramps=len(F.ramps))


def ev_R30(F):
    if not F.circulation or not F.floor_area: return R(False)
    per_storey = F.floor_area / max(F.n_above, 1)
    met = per_storey >= 400
    fr = [w for w in F.walls if w['fire']]
    return R(True, met, ('unknown' if not fr else 'pass') if met else None, unit_area=round(per_storey), n_walls_with_fire_rating=len(fr))


def ev_R31(F):
    return R(len(F.zones) >= 2, True, None, n_zones=len(F.zones))


def ev_R32(F):
    wc = F.sp('wc')
    if not F.public or not wc: return R(False)
    return R(True, True, None if not F.sanitary else 'pass', n_wc_rooms=len(wc), n_sanitary=len(F.sanitary))


def ev_R33(F):
    if not F.usage.startswith('office'): return R(False)
    met = F.n_desks >= 50
    tk = F.sp('kitchen')
    return R(True, met, pf(bool(tk)) if met else None, n_desks=F.n_desks, n_tea_kitchens=len(tk))


def ev_R34(F):
    if not F.usage.startswith('office') or F.n_above < 1: return R(False)
    cl = F.sp('cleaning')
    return R(True, True, 'pass' if cl else 'unknown', n_cleaning_rooms=len(cl))


def ev_R35(F):
    if not F.usage.startswith('office'): return R(False)
    return R(True, True, None, entrance_rooms=len(F.sp('entrance_hall')), canteen=len(F.sp('shop')))


def ev_R36(F):
    sp = [s for s in F.spaces if 'office' in s['cls'] and s['furn']['desk'] >= 4]
    if not sp: return R(False)
    if not F.has_geom: return R(True, True, None)
    bad = [s for s in sp if not s['daylit'] or min(s['size'][:2]) > 15]
    return R(True, True, pf(not bad), n_group_rooms=len(sp), n_far_from_window=len(bad))


def ev_R37(F):
    ds = [n for n in F.byT['IfcFurniture'] + F.byT['IfcFurnishingElement'] if 'desk' in cls(low(n), FURN) and n.get('size_m')]
    if not F.n_desks: return R(False)
    if not ds: return R(True, True, None)
    ok = all(sorted(d['size_m'][:2])[1] >= 1.19 and sorted(d['size_m'][:2])[0] >= 0.6 for d in ds)
    return R(True, True, pf(ok), n=len(ds))


def ev_R38(F):
    sp = [s for s in F.spaces if ('office' in s['cls'] or 'meeting' in s['cls'] or 'edu' in s['cls'])]
    if not sp or not F.windows: return R(bool(sp))
    if not F.has_geom: return R(True, True, None)
    nowin = [s for s in sp if not s['daylit']]
    return R(True, True, pf(not nowin), n_workrooms=len(sp), n_without_window=len(nowin))


def ev_R39(F):
    sp = [s for s in F.spaces if ('office' in s['cls'] or 'meeting' in s['cls']) and s['wins'] and s['size']]
    if not sp: return R(False)
    ratios = []
    for s in sp:
        ww = sum(w.get('overall_width_m') or 0 for w in s['wins'])
        along = max(s['size'][:2]) if s['wins'][0].get('size_m') and s['wins'][0]['size_m'][0] > s['wins'][0]['size_m'][1] and s['size'][0] > s['size'][1] else min(s['size'][:2])
        ratios.append(ww / along if along else 0)
    med = st.median(ratios)
    return R(True, True, pf(med >= 0.65), window_width_ratio_median=round(med, 2), n=len(sp))


def ev_R40(F):
    a = F.sp('archive'); return R(bool(a), True, None, n=len(a))


def ev_R41(F):
    a = F.sp('server'); return R(bool(a), True, None, n=len(a))


def ev_R42(F):
    ws = [round(d['w'] * 1000) for d in F.doors if d['w']]
    if not ws: return R(False)
    bad = [w for w in ws if w % 125 > 12 and (125 - w % 125) > 12]
    return R(True, True, pf(not bad), n_doors=len(ws), n_non_modular=len(bad))


def ev_R43(F):
    ext = [d for d in F.doors if d['ext'] is True]
    if not ext: return R(False)
    rev = [d for d in ext if 'revolv' in d['text'] or 'karussell' in d['text'] or 'sliding' in d['text'] or 'schiebe' in d['text']]
    usable = [d for d in ext if d not in rev]
    return R(True, True, pf(len(usable) >= 1 and (len(ext) >= 2 or F.n_above <= 1)) if F.public else None, n_ext_doors=len(ext), n_revolving_or_sliding=len(rev))


def ev_R44(F):
    if not F.windows: return R(False)
    u = [num(w['props'].get('Pset_WindowCommon.ThermalTransmittance')) for w in F.windows]
    u = [x for x in u if x]
    return R(True, True, 'unknown' if not u else pf(max(u) <= 3.0), n=len(F.windows), n_with_U=len(u), U_max=round(max(u), 2) if u else None)


def ev_R45(F):
    flat = [r for r in F.roofs if (r.get('predefined_type') or '').upper() in ('FLAT_ROOF', 'ROOF') or 'flach' in low(r) or 'flat' in low(r)]
    if not F.roofs: return R(False)
    if F.roof_pitch:
        p = max(F.roof_pitch)
        return R(True, True, pf(p >= 1.1 or p > 10), pitch_deg=p)
    return R(True, True, 'unknown', n_roofs=len(F.roofs), n_flat_named=len(flat))


def ev_R46(F):
    part = [w for w in F.walls if w['ext'] is False and w['lb'] is False]
    return R(bool(part), True, None, n_partitions=len(part))


def ev_R47(F):
    return R(F.usage.startswith('office') and bool(F.slabs), True, None)


def ev_R48(F):
    return R(bool(F.storeys), True, 'unknown', note='no plot area')


def ev_R49(F):
    if not F.spaces: return R(False)
    un = [s for s in F.spaces if not s['cls']]
    return R(True, True, pf(len(un) <= 0.2 * len(F.spaces)), n_spaces=len(F.spaces), n_unclassified=len(un))


def ev_R50(F):
    return R(len(F.elevs) >= 2, True, 'pass' if F.storey_h_typ else None, storey_h=F.storey_h_typ)


def ev_R51(F):
    if not F.usage.startswith('residential'): return R(False)
    return R(True, None, None, extent=F.extent, note='terrace house? not decidable from IFC')


def ev_R52(F):
    if not high_rise(F): return R(False, H_top=F.H_top)
    g = 'I' if F.H_top <= 30 else 'II' if F.H_top <= 60 else 'III' if F.H_top <= 200 else 'IV'
    v = 'pass' if g == 'I' else ('unknown' if not F.has_lift else None)
    return R(True, True, v, group=g, H=F.H_top)


def ev_R53(F):
    if not high_rise(F): return R(False)
    bad = F.usage in ('education', 'health')
    return R(True, bad, pf(not bad) if bad else None, usage=F.usage)


def ev_R54(F):
    if not F.usage.startswith('residential') or not F.flights: return R(False)
    return R(True, None, None, note='number of flats unknown', n_zones=len(F.zones))


def ev_R55(F):
    if not F.spiral: return R(False)
    ok = all(s.get('size_m') and max(s['size_m'][:2]) >= 1.89 for s in F.spiral) if F.has_geom else None
    return R(True, True, pf(ok) if ok is not None else None, n_spiral=len(F.spiral))


def ev_R56(F):
    return R(bool(F.stairs), None, None, note='essential vs non-essential not derivable yet')


def ev_R57(F):
    return R(F.public and bool(F.stairs), True, None)


def ev_R58(F):
    if not F.usage.startswith('residential'): return R(False)
    met = F.n_above > 5
    return R(True, met, pf(F.has_lift) if met else None, n_storeys=F.n_above, has_lift=F.has_lift)


def ev_R59(F):
    if not F.usage.startswith('residential') or F.has_lift: return R(False)
    return R(True, None, None, n_storeys=F.n_above, note='flats per floor unknown')


def ev_R60(F):
    if not high_rise(F) or F.H_top <= 30: return R(False)
    return R(True, True, pf(F.has_lift) if not F.has_lift else 'unknown', H=F.H_top)


def ev_R61(F):
    return R(high_rise(F) and bool(F.stairs), True, None)


def ev_R62(F):
    return R(high_rise(F) and F.has_lift, True, None, n_lifts=len(F.lifts))


def ev_R63(F):
    if not F.usage.startswith('residential'): return R(False)
    met = len(F.zones) > 2 or F.n_above >= 3
    return R(True, met if F.zones else None, None, n_zones=len(F.zones))


def ev_R64(F):
    if not high_rise(F) or not F.corridors: return R(False)
    ws = [c['W'] for c in F.corridors if c['W']]
    return R(True, True, pf(min(ws) >= 1.24) if ws else None, w_min=round(min(ws), 2) if ws else None)


def ev_R65(F):
    if not F.circulation: return R(False)
    Ls = [c['L'] for c in F.circulation if c['L']]
    if not Ls: return R(True, None, None)
    met = max(Ls) > 30
    sd = [d for d in F.doors if d['fire'] or 'rauch' in d['text'] or 'smoke' in d['text'] or 'brandschutz' in d['text'] or 'fire' in d['text'] or 't30' in d['text'] or 't90' in d['text']]
    return R(True, met, ('pass' if sd else 'fail') if met else None, L_max=round(max(Ls), 1), n_fire_or_smoke_doors=len(sd))


def ev_R66(F):
    if not F.usage.startswith('residential') or not F.spaces: return R(False)
    return R(True, True, 'pass' if all(s['area'] for s in F.spaces) else 'unknown', n_spaces=len(F.spaces), src=F.spaces[0]['area_src'])


def ev_R67(F):
    if not F.usage.startswith('residential'): return R(False)
    return R(True, None, None, living=len(F.sp('living')), bed=len(F.sp('bed')))


def ev_R68(F):
    if not F.usage.startswith('residential'): return R(False)
    k = F.sp('kitchen') or [s for s in F.spaces if s['furn']['cook']]
    b = F.sp('wc') or [s for s in F.spaces if s['furn']['wc'] or s['furn']['bath'] or s['furn']['shower']]
    s_ = F.sp('storage')
    return R(True, True, pf(bool(k) and bool(b) and bool(s_)) if (k and b) else ('fail' if F.spaces else None), kitchens=len(k), bathrooms=len(b), storerooms=len(s_))


def ev_R69(F):
    if not F.usage.startswith('residential'): return R(False)
    s_ = [s for s in F.sp('storage') if s['area']]
    return R(True, True, pf(any(s['area'] >= 1 for s in s_)) if s_ else 'fail', n_store=len(s_))


def ev_R70(F):
    return R(F.usage.startswith('office') and bool(F.sp('office')) and bool(F.walls) and any(w['glass'] for w in F.walls if w['ext'] is False), None, None)


def ev_R71(F):
    if not F.public or not F.spaces: return R(False)
    small = [s for s in F.spaces if s['size'] and min(s['size'][:2]) < 1.5 and not ({'stair', 'lift', 'storage'} & s['cls'])]
    ws = [c['W'] for c in F.corridors if c['W']]
    if not F.has_geom: return R(True, True, None)
    return R(True, True, pf(not small and (not ws or min(ws) >= 1.49)), n_rooms_narrower_1_5=len(small), corridor_w_min=round(min(ws), 2) if ws else None)


def ev_R72(F):
    if not F.public or not F.corridors: return R(False)
    long_ = [c for c in F.corridors if c['L'] and c['L'] > 15]
    if not F.has_geom: return R(True, None, None)
    bad = [c for c in long_ if c['W'] < 1.79]
    return R(True, bool(long_), pf(not bad) if long_ else None, n_corridors_over_15m=len(long_), n_narrower_1_8=len(bad))


def ev_R73(F):
    if not F.usage.startswith('residential') or not F.sp('wc'): return R(False)
    return R(True, None, None, note='accessible flat not identified', n_sanitary=len(F.sanitary))


def ev_R74(F):
    liv = [s for s in F.sp('living') if s['area']]
    if not F.usage.startswith('residential') or not liv: return R(False)
    return R(True, None, None, living_area_min=round(min(s['area'] for s in liv), 1))


def ev_R75(F):
    return R(F.usage.startswith('residential') and F.has_geom and bool(F.furn_all), None, None)


def ev_R76(F):
    hab = [s for s in F.spaces if ({'living', 'bed'} & s['cls']) and s['area']]
    if not F.usage.startswith('residential') or not hab: return R(False)
    small = [s for s in hab if s['area'] < 8]
    low_ = [s for s in hab if s['h'] and s['h'] < 2.39]
    win = None
    if F.has_geom:
        bad = [s for s in hab if s['wins'] and sum((w.get('overall_width_m') or 0) * (w.get('overall_height_m') or 0) for w in s['wins']) < s['area'] / 8]
        win = len(bad)
    v = pf(not small and not low_ and not win) if win is not None else ('fail' if small or low_ else None)
    return R(True, True, v, n_rooms=len(hab), n_under_8m2=len(small), n_under_2_40=len(low_), n_window_under_1_8=win)


def ev_R77(F):
    b = [s for s in F.sp('balcony') if s['area']]
    if not F.usage.startswith('residential') or not F.sp('balcony'): return R(False)
    return R(True, True, None, n=len(F.sp('balcony')), area_med=round(st.median([s['area'] for s in b]), 1) if b else None)


def ev_R78(F):
    eh = F.sp('entrance_hall')
    if not F.usage.startswith('residential') or not eh: return R(False)
    if not F.has_geom: return R(True, True, None)
    ok = []
    for h in eh:
        adj = set()
        for d in h['doors']:
            for sp2 in [F.N[x] for x in F.opens_rev(d['id'])]:
                adj |= cls(low(sp2), KW)
        ok.append('kitchen' in adj and 'wc' in adj)
    return R(True, True, pf(any(ok)), n_entrance_halls=len(eh))


def ev_R79(F):
    c = [x for x in F.corridors if x['W']]
    if not F.usage.startswith('residential') or not F.corridors: return R(False)
    return R(True, True, pf(min(x['W'] for x in c) >= 0.99) if c else None, w_min=round(min(x['W'] for x in c), 2) if c else None)


def ev_R80(F):
    if not F.usage.startswith('residential') or len(F.zones) > 1: return R(False)
    ext = [d for d in F.doors if d['ext'] is True]
    st_ = {F.storey_of[d['n']['id']]['elevation_m'] for d in ext if d['n']['id'] in F.storey_of}
    return R(True, True, pf(len(st_) >= min(F.n_above, 2)) if ext else None, storeys_with_external_door=len(st_), n_storeys=F.n_above)


def ev_R81(F):
    ext = [d for d in F.doors if d['ext'] is True]
    return R(F.usage.startswith('residential') and bool(ext), None, None, n_ext_doors=len(ext))


def ev_R82(F):
    wc = F.sp('wc')
    if not wc: return R(False)
    typed = [s for s in wc if s['furn']['wc'] or s['furn']['bath'] or s['furn']['shower']]
    return R(True, True, 'pass' if typed else 'unknown', n_bathrooms=len(wc), n_with_fixtures=len(typed), n_sanitary_terminals=len(F.sanitary))


def ev_R83(F):
    h = [s for s in F.sp('hall_assembly', 'meeting') if s['area'] and s['h'] and s['furn']['chair']]
    if not F.sp('hall_assembly', 'meeting'): return R(False)
    if not h: return R(True, True, None)
    v = [s['area'] * s['h'] / s['furn']['chair'] for s in h]
    return R(True, True, pf(min(v) >= 4), m3_per_person_min=round(min(v), 1), n=len(h))


def ev_R84(F):
    k = [s for s in F.sp('kitchen') if s['area'] and s['area'] > 30] + [s for s in F.spaces if s['furn']['cook'] >= 3]
    return R(bool(k) and bool(F.sp('shop')), None, None, n=len(k))


def ev_R85(F):
    s_ = F.sp('seminar')
    if not s_: return R(False)
    per = [x['area'] / x['furn']['chair'] for x in s_ if x['area'] and x['furn']['chair']]
    return R(True, True, pf(all(1.5 <= p <= 3 for p in per)) if per else None, n=len(s_))


def ev_R86(F):
    return R(F.usage == 'education' and bool(F.sp('office')), None, None)


def ev_R87(F):
    if not F.public or not F.circulation: return R(False)
    if not F.has_geom: return R(True, True, None)
    bad = [c for c in F.circulation if sum(c['sp']['furn'][k] for k in ('sofa', 'table', 'chair', 'desk')) > 0]
    return R(True, True, pf(not bad), n_corridors=len(F.circulation), n_with_furniture=len(bad))


def ev_R88(F):
    sp = [s for s in F.spaces if 'office' in s['cls'] and s['furn']['desk'] >= 10 and s['size']]
    if not sp: return R(False)
    d = [min(s['size'][:2]) for s in sp]
    return R(True, True, None, n_open_plan=len(sp), depth_max=round(max(d), 1))


def ev_R89(F):
    return R(F.n_desks > 0 and bool(F.windows), None, None, note='desk orientation not extracted')


def ev_R90(F):
    m = [s for s in F.sp('mail') if 'office' not in s['cls']]
    return R(F.usage.startswith('office') and bool(m), True, None, n=len(m))


def ev_R91(F):
    if not F.usage.startswith('residential'): return R(False)
    ws = [d['w'] for d in F.doors if d['w'] and not d['ext']]
    if not ws: return R(True, True, None)
    return R(True, True, pf(min(ws) >= 0.55 and st.median(ws) >= 0.75), w_min=round(min(ws), 2), w_med=round(st.median(ws), 2))


def ev_R92(F):
    return R(F.usage.startswith('residential') and F.has_lift, None, None, note='flat entrance doors not identified')


def ev_R93(F):
    if F.n_above < 2 or not F.windows: return R(False)
    met = len(F.stairs) < 2
    if not met: return R(True, False, None, n_stairs=len(F.stairs))
    ok = [w for w in F.windows if (w['w'] or 0) >= 0.9 and (w['h'] or 0) >= 1.2 and (w['sill'] is None or w['sill'] <= 1.2)]
    return R(True, True, pf(bool(ok)), n_stairs=len(F.stairs), n_windows_ok=len(ok))


def ev_R94(F):
    return R(high_rise(F) and bool(F.ext_walls or F.curtain), True, None)


def ev_R95(F):
    sl = [w for w in F.ext_walls if w['n_layers'] == 1 and w['masonry'] and not w['insul']]
    if not sl: return R(False, n_ext=len(F.ext_walls))
    hi = [w for w in sl if any(k in w['names'] for k in ['poren', 'aerated', 'ytong', 'poroton', 'leicht', 'light', 'thermo', 'hochloch', 'dämm'])]
    return R(True, True, 'pass' if len(hi) == len(sl) else 'unknown', n_single_leaf=len(sl), n_high_insulation_named=len(hi))


def ev_R96(F):
    cv = [w for w in F.ext_walls if w['n_layers'] >= 2 and w['masonry'] and (w['air'] or w['insul']) and sum(1 for l in w['mat'].get('layers', []) if any(k in (l.get('name') or '').lower() for k in ['ziegel', 'brick', 'mauer', 'ks', 'kalksand', 'block', 'masonry'])) >= 2]
    if not cv: return R(False)
    ok = []
    for w in cv:
        air = [l for l in w['mat'].get('layers', []) if any(k in (l.get('name') or '').lower() for k in ['air', 'luft', 'cavity'])]
        ok.append(all(0.04 <= (l.get('thickness_m') or 0) <= 0.15 for l in air) if air else True)
    return R(True, True, pf(all(ok)), n_cavity_walls=len(cv))


def ev_R97(F):
    rv = [w for w in F.ext_walls if w['air'] and ('hinterlüft' in w['names'] or 'ventilat' in w['names'] or 'rear' in w['names'])]
    return R(bool(rv), True, None, n=len(rv))


def ev_R98(F):
    if not F.ext_walls: return R(False)
    u = [w['u'] for w in F.ext_walls if w['u']]
    return R(True, True, 'unknown' if not u else 'pass', n_with_U=len(u), n_ext=len(F.ext_walls))


def ev_R99(F):
    g = any(k in F.roof_names for k in ['gründach', 'gruendach', 'green', 'substrat', 'vegetat', 'begrün', 'extensiv', 'intensiv'])
    if not F.roofs: return R(False)
    return R(g, True if g else None, (pf(max(F.roof_pitch) <= 25) if F.roof_pitch else 'unknown') if g else None)


def ev_R100(F):
    pitched = [r for r in F.roofs if (r.get('predefined_type') or '') in ('GABLE_ROOF', 'HIP_ROOF', 'SHED_ROOF', 'GAMBREL_ROOF', 'MANSARD_ROOF', 'BUTTERFLY_ROOF', 'PAVILION_ROOF', 'DOME_ROOF', 'BARREL_ROOF') or 'sattel' in low(r) or 'walm' in low(r) or 'pult' in low(r) or 'gable' in low(r) or 'hip' in low(r) or 'pitch' in low(r)] or [r for r in F.roofs if F.roof_pitch and max(F.roof_pitch) > 10]
    if not pitched: return R(False, n_roofs=len(F.roofs))
    vb = any(k in F.roof_names for k in ['dampf', 'vapour', 'vapor'])
    ins = any(k in F.roof_names for k in ['dämm', 'insul', 'wool', 'wolle'])
    return R(True, True, ('pass' if vb else 'unknown') if ins else 'unknown', n_pitched=len(pitched), insulation_named=ins, vapour_barrier_named=vb)


def ev_R101(F):
    if not F.usage.startswith('residential') or len(F.zones) < 2: return R(False)
    return R(True, None, None, note='party wall needs zone-of-both-sides')


def ev_R102(F):
    th = [round((w['total'] or 0) * 1000) for w in F.walls if w['total']]
    if not th and not F.grids: return R(False)
    if not th: return R(True, True, None, grids=len(F.grids))
    mod = [t for t in th if t % 25 == 0 or t in (115, 175, 240, 300, 365, 490)]
    return R(True, True, pf(len(mod) >= 0.8 * len(th)), n_walls_with_thickness=len(th), n_modular=len(mod))


def ev_R103(F):
    if not high_rise(F) or not F.windows: return R(False)
    fixed = [w for w in F.windows if 'FIXED' in w['op'].upper() or 'fest' in w['text'] or 'fixed' in w['text']]
    return R(True, bool(fixed or F.curtain), None, n_fixed=len(fixed), n_curtain=len(F.curtain))


EV = {k[3:]: v for k, v in dict(globals()).items() if k.startswith('ev_R')}


def evaluate(G):
    F = Facts(G)
    out = {'model': F.model, 'usage': F.usage, 'usage_scores': F.usage_scores, 'n_storeys_above': F.n_above, 'H_top': F.H_top, 'n_spaces': F.n_spaces,
           'n_stairs': len(F.stairs), 'n_doors': len(F.doors), 'n_desks': F.n_desks, 'has_lift': F.has_lift, 'has_geom': F.has_geom, 'rules': {}}
    for rid in RULES:
        fn = EV.get(rid)
        try:
            out['rules'][rid] = fn(F) if fn else {'context': None}
        except Exception as ex:
            out['rules'][rid] = {'context': None, 'error': f'{type(ex).__name__}: {str(ex)[:80]}'}
    return out


def main():
    paths = sorted(glob.glob(os.path.join(GRAPHS, 'ifc4_*.json')))
    if len(sys.argv) > 1:
        paths = [p for p in paths if os.path.basename(p).startswith(sys.argv[1])]
    os.makedirs(OUTDIR, exist_ok=True)
    rows = []
    for p in paths:
        try:
            G = json.load(open(p))
        except Exception as ex:
            print('skip', p, ex); continue
        rows.append(evaluate(G))
    if len(sys.argv) > 1:
        for r in rows:
            print(json.dumps({k: v for k, v in r.items() if k != 'rules'}, ensure_ascii=False))
            for rid, x in r['rules'].items():
                print(f"  {rid:5} ctx={x.get('context')!s:5} cond={x.get('condition')!s:5} verdict={x.get('verdict')!s:8} {x.get('note', '') or x.get('error', '')}")
        return
    with open(os.path.join(OUTDIR, 'matches.jsonl'), 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    # summary per rule
    summ = []
    for rid, rule in RULES.items():
        c = collections.Counter()
        for r in rows:
            x = r['rules'].get(rid, {})
            if x.get('error'): c['error'] += 1
            if x.get('context'): c['context'] += 1
            if x.get('context') and x.get('condition') is True: c['fires'] += 1
            if x.get('context') and x.get('condition') is None: c['cond_unknown'] += 1
            v = x.get('verdict')
            if v: c[v] += 1
        summ.append(dict(rid=rid, title=rule['title'], level=rule['level'], modality=rule['modality'], concreteness=(rule.get('context') or {}).get('concreteness', ''),
                         n_models=len(rows), context=c['context'], fires=c['fires'], cond_unknown=c['cond_unknown'], **{k: c[k] for k in ('pass', 'fail', 'mixed', 'unknown')}, errors=c['error']))
    summ.sort(key=lambda s: (-s['fires'], -s['context'], int(s['rid'][1:])))
    usage = collections.Counter(r['usage'] for r in rows)
    meta = dict(n_models=len(rows), usage=dict(usage), with_geom=sum(1 for r in rows if r['has_geom']), high_rise=sum(1 for r in rows if (r['H_top'] or 0) > 22),
                storeys=dict(collections.Counter(min(r['n_storeys_above'], 9) for r in rows)))
    json.dump(dict(meta=meta, rules=summ), open(os.path.join(HERE, 'scan370_summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import csv
    with open(os.path.join(OUTDIR, 'summary.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(summ[0].keys())); w.writeheader(); w.writerows(summ)
    with open(os.path.join(OUTDIR, 'summary.md'), 'w', encoding='utf-8') as fh:
        fh.write(f"# 103 rules × {len(rows)} models\n\nusage (from room names): {dict(usage)}; graphs with geometry: {meta['with_geom']}; high-rise (> 22 m): {meta['high_rise']}\n\n")
        fh.write('| rank | rule | level | context matched | fires (IF true) | pass | fail | mixed | unknown |\n|---|---|---|---|---|---|---|---|---|\n')
        for i, s in enumerate(summ, 1):
            fh.write(f"| {i} | {s['rid']} {s['title']} | {s['level']} | {s['context']} | {s['fires']} | {s['pass']} | {s['fail']} | {s['mixed']} | {s['unknown']} |\n")
    print(f"{len(rows)} models scanned; usage {dict(usage)}")
    for s in summ[:15]:
        print(f"{s['rid']:5} ctx={s['context']:4} fires={s['fires']:4} pass={s['pass']:4} fail={s['fail']:4} unk={s['unknown']:4}  {s['title']}")


if __name__ == '__main__':
    main()
