"""Per-model IFC fact sheet used to write knowledge-hidden QAs.

Usage (needs ifcopenshell + numpy):  python tools/facts.py proj1,proj2 facts/
Writes facts/<project>.json: storeys, spaces (area, height, geometry bbox), doors (type, size,
operation, bounding spaces), windows (size, approx. sill, bounding spaces), stairs (risers,
tread, width), railings (height), furniture per containing/geometric space.
"""
import ifcopenshell, ifcopenshell.util.element as E, ifcopenshell.util.placement as PL, ifcopenshell.util.unit as U
import ifcopenshell.geom as G, numpy as np
import json, sys, os, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'ifc_bench')
GS = G.settings(); GS.set('use-world-coords', True)

def num(v): return round(v, 3) if isinstance(v, float) else v
def first(ps, keys):
    for pn, d in ps.items():
        for k in keys:
            if k in d and isinstance(d[k], (int, float)) and d[k] > 0: return d[k], f'{pn}.{k}'
    return None, None
def bbox(el):
    try:
        sh = G.create_shape(GS, el); v = np.array(sh.geometry.verts).reshape(-1, 3); return v.min(0), v.max(0)
    except Exception: return None
def storey_of(el):
    c = E.get_container(el)
    while c is not None and not c.is_a('IfcBuildingStorey'): c = E.get_aggregate(c)
    return c.Name if c else None

def run(p, out_dir):
    f = ifcopenshell.open(os.path.join(ROOT, p, 'arc.ifc'))
    L = U.calculate_unit_scale(f); A = U.calculate_unit_scale(f, 'AREAUNIT')
    st = {s.id(): (s.Name, (s.Elevation or 0) * L) for s in f.by_type('IfcBuildingStorey')}
    out = dict(project=p, schema=f.schema, length_unit_scale=L, storeys=sorted([(n, round(e, 3)) for n, e in st.values()], key=lambda x: x[1]))
    spaces, sbox = [], {}
    for s in f.by_type('IfcSpace'):
        ps = E.get_psets(s)
        a, asrc = first(ps, ['NetFloorArea', 'GrossFloorArea', 'Area'])
        h, hsrc = first(ps, ['FinishCeilingHeight', 'ClearHeight', 'Height', 'UnboundedHeight', 'Unbounded Height', 'GrossHeight', 'Limit Offset'])
        bb = bbox(s); dims = [round(float(x), 2) for x in (bb[1] - bb[0])] if bb is not None else None
        if bb is not None: sbox[s.id()] = bb
        agg = E.get_aggregate(s)
        spaces.append(dict(gid=s.GlobalId, name=s.Name, longname=s.LongName, storey=agg.Name if agg and agg.is_a('IfcBuildingStorey') else storey_of(s),
                           area=num(a * A) if a else None, area_src=asrc,
                           height=num(h * L) if h and h > 20 else num(h) if h else None, height_src=hsrc, bbox_xyz=dims))
    out['spaces'] = spaces
    label = {s.id(): (s.LongName or s.Name) for s in f.by_type('IfcSpace')}
    bnd = collections.defaultdict(set)
    for rb in f.by_type('IfcRelSpaceBoundary'):
        el, sp = rb.RelatedBuildingElement, rb.RelatingSpace
        if el and sp and sp.is_a('IfcSpace') and (el.is_a('IfcDoor') or el.is_a('IfcWindow')): bnd[el.id()].add(label[sp.id()])
    def in_space(el):
        if bnd.get(el.id()): return sorted(bnd[el.id()])
        bb = bbox(el)
        if bb is None: return []
        c = (bb[0] + bb[1]) / 2
        return sorted({label[i] for i, (a, b) in sbox.items() if a[0] - .15 <= c[0] <= b[0] + .15 and a[1] - .15 <= c[1] <= b[1] + .15 and a[2] - .6 <= c[2] <= b[2]})
    def tname(el):
        t = E.get_type(el); return t.Name if t else None
    def op(el):
        t = E.get_type(el)
        return getattr(el, 'OperationType', None) or (getattr(t, 'OperationType', None) if t else None) or getattr(el, 'PredefinedType', None)
    out['doors'] = []
    for d in f.by_type('IfcDoor'):
        ps = E.get_psets(d)
        out['doors'].append(dict(gid=d.GlobalId, name=d.Name, type=tname(d), op=str(op(d)), width=num((d.OverallWidth or 0) * L) or None,
                                 height=num((d.OverallHeight or 0) * L) or None, storey=storey_of(d), spaces=in_space(d),
                                 fire=next((v.get('FireRating') for v in ps.values() if v.get('FireRating')), None),
                                 external=next((v.get('IsExternal') for v in ps.values() if 'IsExternal' in v), None)))
    out['windows'] = []
    for w in f.by_type('IfcWindow'):
        sill = None
        try:
            z = PL.get_local_placement(w.ObjectPlacement)[2][3] * L
            se = next((e for n, e in st.values() if n == storey_of(w)), None)
            if se is not None: sill = round(z - se, 3)
        except Exception: pass
        out['windows'].append(dict(gid=w.GlobalId, name=w.Name, type=tname(w), width=num((w.OverallWidth or 0) * L) or None,
                                   height=num((w.OverallHeight or 0) * L) or None, storey=storey_of(w), sill_approx=sill, spaces=in_space(w)))
    out['stairs'] = []
    for s in f.by_type('IfcStair') + f.by_type('IfcStairFlight'):
        ps = E.get_psets(s); sc = ps.get('Pset_StairCommon') or ps.get('Pset_StairFlightCommon') or {}
        flat = {f'{pn}.{k}': num(v) for pn, d in ps.items() for k, v in d.items() if isinstance(v, (int, float)) and any(x in k.lower() for x in ['riser', 'tread', 'width', 'run', 'step', 'going'])}
        out['stairs'].append(dict(gid=s.GlobalId, cls=s.is_a(), name=s.Name, predefined=str(getattr(s, 'PredefinedType', None)), storey=storey_of(s),
                                  n_riser=sc.get('NumberOfRiser'), riser=num(sc.get('RiserHeight')), tread=num(sc.get('TreadLength')), props=flat))
    out['railings'] = []
    for r in f.by_type('IfcRailing'):
        h, _ = first(E.get_psets(r), ['Height', 'RailingHeight'])
        out['railings'].append(dict(name=r.Name, type=tname(r), storey=storey_of(r), height=num(h * L if h and h > 20 else h) if h else None))
    furn = collections.Counter()
    for x in f.by_type('IfcFurnishingElement'):
        furn[(', '.join(in_space(x)) or storey_of(x), (tname(x) or x.Name or '').split(':')[0])] += 1
    out['furniture'] = [dict(where=k[0], item=k[1], n=v) for k, v in sorted(furn.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))]
    out['other_counts'] = {k: len(f.by_type(k)) for k in ['IfcCurtainWall', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcRoof', 'IfcTransportElement', 'IfcRelSpaceBoundary']}
    json.dump(out, open(os.path.join(out_dir, f'{p}.json'), 'w'), ensure_ascii=False, indent=1, default=str)
    print(p, 'spaces', len(spaces), 'doors', len(out['doors']), 'wins', len(out['windows']), 'stairs', len(out['stairs']), flush=True)

for p in sys.argv[1].split(','): run(p, sys.argv[2])
