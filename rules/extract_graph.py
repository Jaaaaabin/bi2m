"""IFC → graph.json: the rule-matching layer described in rules/PILOT.md.

Nodes = rule-relevant IFC entities (site, building, storeys, spaces, stairs + flights, doors, windows, walls, slabs,
roofs, columns, lifts, furniture, sanitary terminals, zones, grids) with the attributes the rules read: names,
Psets/Qtos we care about, material layers, world bbox. Edges = IFC relations copied as they are (containedIn,
aggregates, hasType, fillsOpening, boundedBy when the file has IfcRelSpaceBoundary) plus geometry-derived ones
(space CONTAINS element, door CONNECTS two spaces, stair SERVES storeys), tagged source: 'ifc' | 'derived'.
Building-level facts IFC does not hold (usage, public access) go in `facts` with source 'model_card' or 'inferred'.

.venv/bin/python rules/extract_graph.py data/model_ifc4_0001-0370/0204.ifc runs/graphs/ifc4_0204.json [--no-geom]
"""
import json, sys, os, time, collections, math
import ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element as ue, ifcopenshell.util.unit as uu, ifcopenshell.util.placement as up

NODE_TYPES = ['IfcSite', 'IfcBuilding', 'IfcBuildingStorey', 'IfcSpace', 'IfcStair', 'IfcStairFlight', 'IfcRamp', 'IfcRampFlight',
              'IfcDoor', 'IfcWindow', 'IfcWall', 'IfcCurtainWall', 'IfcSlab', 'IfcRoof', 'IfcColumn', 'IfcBeam', 'IfcRailing',
              'IfcTransportElement', 'IfcFurniture', 'IfcFurnishingElement', 'IfcSanitaryTerminal', 'IfcZone', 'IfcGrid', 'IfcCovering']
PSET_KEEP = {'Pset_WallCommon', 'Pset_DoorCommon', 'Pset_WindowCommon', 'Pset_SpaceCommon', 'Pset_StairCommon', 'Pset_StairFlightCommon',
             'Pset_SlabCommon', 'Pset_RoofCommon', 'Pset_BuildingCommon', 'Pset_BuildingStoreyCommon', 'Pset_SiteCommon',
             'Pset_TransportElementCommon', 'Pset_RampCommon', 'Pset_RailingCommon', 'Pset_ColumnCommon', 'Pset_CurtainWallCommon',
             'Pset_SpaceFireSafetyRequirements', 'Pset_SpaceOccupancyRequirements', 'Pset_CoveringCommon'}
PROP_KEEP = {'IsExternal', 'LoadBearing', 'FireRating', 'ThermalTransmittance', 'AcousticRating', 'NumberOfRiser', 'NumberOfTreads',
             'RiserHeight', 'TreadLength', 'NosingLength', 'WalkingLineOffset', 'TreadLengthAtOffset', 'TreadLengthAtInnerSide',
             'Reference', 'Category', 'OccupancyType', 'OccupancyNumber', 'HandicapAccessible', 'Compartmentation', 'IsLandmarked',
             'NumberOfStoreys', 'GrossPlannedArea', 'NetPlannedArea', 'PitchAngle', 'ProjectedArea', 'TotalArea', 'Span', 'CapacityPeople',
             'CapacityWeight', 'FireExit', 'SelfClosing', 'SmokeStop', 'GlazingAreaFraction', 'EntranceLevel', 'AboveGround', 'Slope', 'Height',
             'Width', 'Length', 'Depth', 'Thickness', 'BuildingHeightLimit', 'TotalArea', 'FloorArea', 'IsSprinklered', 'ExtendToStructure'}


def num(v):
    return round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def props(e):
    out = {}
    for pname, d in ue.get_psets(e).items():
        if not isinstance(pname, str) or not isinstance(d, dict):
            continue
        if pname in PSET_KEEP or pname.startswith('Qto_'):
            for k, v in d.items():
                if k == 'id':
                    continue
                if pname.startswith('Qto_') or k in PROP_KEEP:
                    if isinstance(v, (int, float, str, bool)):
                        out[f'{pname}.{k}'] = num(v)
    return out


def layers(e, scale):
    m = ue.get_material(e, should_skip_usage=True)
    if m is None:
        return None
    if m.is_a('IfcMaterialLayerSet'):
        return {'kind': 'layers', 'total_m': round(sum((l.LayerThickness or 0) for l in m.MaterialLayers) * scale, 4),
                'layers': [{'name': l.Material.Name if l.Material else None, 'thickness_m': round((l.LayerThickness or 0) * scale, 4),
                            'category': getattr(l, 'Category', None)} for l in m.MaterialLayers]}
    if m.is_a('IfcMaterialConstituentSet'):
        return {'kind': 'constituents', 'layers': [{'name': c.Material.Name if c.Material else None, 'category': c.Category} for c in m.MaterialConstituents]}
    if m.is_a('IfcMaterialProfileSet'):
        return {'kind': 'profiles', 'layers': [{'name': p.Material.Name if p.Material else None} for p in m.MaterialProfiles]}
    if m.is_a('IfcMaterial'):
        return {'kind': 'single', 'layers': [{'name': m.Name}]}
    if m.is_a('IfcMaterialList'):
        return {'kind': 'list', 'layers': [{'name': x.Name} for x in m.Materials]}
    return {'kind': m.is_a()}


def bbox_of(f, e, settings, cache):
    """World-coordinate bbox of e; aggregates (IfcStair without representation) take the union of their parts."""
    if e.id() in cache:
        return cache[e.id()]
    bb = None
    if e.Representation is not None:
        try:
            shp = ifcopenshell.geom.create_shape(settings, e)
            v = shp.geometry.verts
            xs, ys, zs = v[0::3], v[1::3], v[2::3]
            if xs:
                bb = [round(min(xs), 3), round(min(ys), 3), round(min(zs), 3), round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)]
        except Exception:
            bb = None
    if bb is None:
        parts = [p for r in (e.IsDecomposedBy or []) for p in r.RelatedObjects]
        boxes = [b for b in (bbox_of(f, p, settings, cache) for p in parts) if b]
        if boxes:
            bb = [min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
                  max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes)]
    cache[e.id()] = bb
    return bb


def inside(bb, cont, zslack=0.05):
    """centre of bb inside cont's footprint and z-range (with slack)."""
    cx, cy, cz = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2
    return cont[0] - 0.02 <= cx <= cont[3] + 0.02 and cont[1] - 0.02 <= cy <= cont[4] + 0.02 and cont[2] - zslack <= cz <= cont[5] + zslack


def overlap_xy(a, b, pad=0.3):
    return not (a[3] + pad < b[0] or b[3] + pad < a[0] or a[4] + pad < b[1] or b[4] + pad < a[1])


def main():
    src, dst = sys.argv[1], sys.argv[2]
    geom = '--no-geom' not in sys.argv
    t0 = time.time()
    f = ifcopenshell.open(src)
    scale = uu.calculate_unit_scale(f)
    settings = None
    if geom:
        settings = ifcopenshell.geom.settings()
        settings.set('use-world-coords', True)
    cache = {}
    nodes, edges = {}, []

    def add_node(e):
        n = {'id': e.GlobalId, 'type': e.is_a(), 'name': e.Name, 'long_name': getattr(e, 'LongName', None), 'step': e.id()}
        if e.is_a('IfcDoor') or e.is_a('IfcWindow'):
            n['overall_height_m'] = num((e.OverallHeight or 0) * scale) if e.OverallHeight else None
            n['overall_width_m'] = num((e.OverallWidth or 0) * scale) if e.OverallWidth else None
            n['predefined_type'] = getattr(e, 'PredefinedType', None)
            n['operation_type'] = getattr(e, 'OperationType', None) or getattr(e, 'PartitioningType', None)
        if e.is_a('IfcBuildingStorey'):
            n['elevation_m'] = num((e.Elevation or 0) * scale)
        if e.is_a('IfcSite'):
            n['ref_elevation_m'] = num((e.RefElevation or 0) * scale) if e.RefElevation is not None else None
            n['ref_latitude'] = e.RefLatitude
            n['ref_longitude'] = e.RefLongitude
        if hasattr(e, 'PredefinedType') and 'predefined_type' not in n:
            n['predefined_type'] = e.PredefinedType
        if e.is_a('IfcSpace') or e.is_a('IfcBuilding') or e.is_a('IfcBuildingStorey'):
            n['description'] = e.Description
        t = ue.get_type(e)
        if t is not None:
            n['type_name'] = t.Name
            edges.append({'s': e.GlobalId, 'p': 'hasType', 'o': t.GlobalId, 'source': 'ifc'})
            tp = props(t)
            for k, v in tp.items():
                n.setdefault('props', {}).setdefault(k, v)
        p = props(e)
        if p:
            n['props'] = {**n.get('props', {}), **p}
        lay = layers(e, scale)
        if lay:
            n['material'] = lay
        c = ue.get_container(e)
        if c is not None:
            edges.append({'s': e.GlobalId, 'p': 'containedIn', 'o': c.GlobalId, 'source': 'ifc'})
        for r in (e.Decomposes or []):
            edges.append({'s': e.GlobalId, 'p': 'partOf', 'o': r.RelatingObject.GlobalId, 'source': 'ifc'})
        if e.is_a('IfcDoor') or e.is_a('IfcWindow'):
            for r in (e.FillsVoids or []):
                host = r.RelatingOpeningElement.VoidsElements[0].RelatingBuildingElement if r.RelatingOpeningElement.VoidsElements else None
                if host is not None:
                    edges.append({'s': e.GlobalId, 'p': 'fillsOpeningIn', 'o': host.GlobalId, 'source': 'ifc'})
        if geom and not e.is_a('IfcZone') and not e.is_a('IfcGrid') and not e.is_a('IfcSite') and not e.is_a('IfcBuilding'):
            bb = bbox_of(f, e, settings, cache)
            if bb:
                n['bbox'] = bb
                n['size_m'] = [round(bb[3] - bb[0], 3), round(bb[4] - bb[1], 3), round(bb[5] - bb[2], 3)]
        nodes[e.GlobalId] = n

    errors = 0
    for t in NODE_TYPES:
        for e in f.by_type(t):
            if e.GlobalId not in nodes:
                try:
                    add_node(e)
                except Exception as ex:
                    errors += 1
                    nodes[e.GlobalId] = {'id': e.GlobalId, 'type': e.is_a(), 'name': e.Name, 'step': e.id(), 'error': str(ex)[:120]}
    # IfcRelSpaceBoundary (if any)
    for r in f.by_type('IfcRelSpaceBoundary'):
        if r.RelatedBuildingElement is not None and r.RelatingSpace is not None and hasattr(r.RelatingSpace, 'GlobalId'):
            edges.append({'s': r.RelatingSpace.GlobalId, 'p': 'boundedBy', 'o': r.RelatedBuildingElement.GlobalId, 'source': 'ifc'})
    # zones
    for z in f.by_type('IfcZone'):
        for r in (z.IsGroupedBy or []):
            for o in r.RelatedObjects:
                edges.append({'s': o.GlobalId, 'p': 'inZone', 'o': z.GlobalId, 'source': 'ifc'})

    # ── derived edges ──
    if geom:
        spaces = [n for n in nodes.values() if n['type'] == 'IfcSpace' and n.get('bbox')]
        storeys = sorted([n for n in nodes.values() if n['type'] == 'IfcBuildingStorey'], key=lambda s: s['elevation_m'])
        for n in nodes.values():
            if n['type'] in ('IfcFurniture', 'IfcFurnishingElement', 'IfcSanitaryTerminal', 'IfcColumn') and n.get('bbox'):
                for s in spaces:
                    if inside(n['bbox'], s['bbox']):
                        edges.append({'s': s['id'], 'p': 'contains', 'o': n['id'], 'source': 'derived'})
                        break
            if n['type'] in ('IfcDoor', 'IfcWindow') and n.get('bbox'):
                bb = n['bbox']
                cz = (bb[2] + bb[5]) / 2
                near = [s for s in spaces if s['bbox'][2] - 0.3 <= cz <= s['bbox'][5] + 0.3 and overlap_xy(bb, s['bbox'], pad=0.35)]
                for s in near[:4]:
                    edges.append({'s': n['id'], 'p': 'opensTo', 'o': s['id'], 'source': 'derived'})
            if n['type'] in ('IfcStair', 'IfcRamp', 'IfcTransportElement') and n.get('bbox'):
                z0, z1 = n['bbox'][2], n['bbox'][5]
                for s in storeys:
                    if z0 - 0.3 <= s['elevation_m'] <= z1 + 0.3:
                        edges.append({'s': n['id'], 'p': 'serves', 'o': s['id'], 'source': 'derived'})

    summary = collections.Counter(n['type'] for n in nodes.values())
    out = {'model': os.path.splitext(os.path.basename(src))[0], 'source_file': src, 'schema': f.schema,
           'header': {'description': list(f.header.file_description.description), 'originating_system': f.header.file_name.originating_system,
                      'preprocessor': f.header.file_name.preprocessor_version},
           'unit_scale_to_m': scale, 'facts': [], 'node_counts': dict(summary), 'edge_counts': dict(collections.Counter((e['p'], e['source']) for e in edges)),
           'nodes': list(nodes.values()), 'edges': edges, 'extract_seconds': round(time.time() - t0, 1), 'node_errors': errors}
    out['edge_counts'] = {f'{k[0]}({k[1]})': v for k, v in collections.Counter((e['p'], e['source']) for e in edges).items()}
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    json.dump(out, open(dst, 'w'), ensure_ascii=False, indent=None)
    print(f"{out['model']}: {len(nodes)} nodes, {len(edges)} edges, {out['extract_seconds']}s → {dst}")
    print(' nodes:', dict(summary))
    print(' edges:', out['edge_counts'])


if __name__ == '__main__':
    main()
