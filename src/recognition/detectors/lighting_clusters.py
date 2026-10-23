"""Lighting clusters: IfcWindow instances of the SAME window type
(IfcRelDefinesByType), clustered by spatial (x, y) proximity ACROSS ALL
FLOORS - replaces this category's earlier "Horizontal Window Sightline"
version (scope=storey, grouped by (storey, exterior-view verdict)) per
explicit request: instead of "which windows on this ONE floor are clear",
the question is now "which windows, of the SAME type, sit near each other
anywhere in the building" - a repeated window family concentrated in one
area reads as one daylight zone regardless of which floor each instance is
actually on.

Distinct from window_alignment.py's vertical bay stacking (exact (x, y)
match within DEFAULT_COLUMN_TOLERANCE_M-scale tolerance, the same as
column matching): a lighting cluster's own proximity threshold is much
looser (DEFAULT_CLUSTER_DISTANCE_M) - confirmed empirically against
data/test_1.ifc's own window layout: one continuous window row/ribbon
(the same IfcWindowType repeated along one wall) has ~2-3.5m gaps between
consecutive instances, while the gap to the next genuinely different
section/wing of the building is 10m+. DEFAULT_CLUSTER_DISTANCE_M=7m widens
this on top of that first empirical gap - a deliberately MORE inclusive
threshold than the minimum needed to just bridge one ribbon, per explicit
request ("clusters a bit more inclusive") - while still staying clear of
the real cliff: re-run at 5/7/7.5/8/10m on both data/test_1.ifc and
data/test_5.ifc showed 7-7.5m as a genuine plateau (byte-identical cluster
counts/sizes on both files), whereas 10m collapses data/test_5.ifc from 10
clusters to 4 (one balloons to 43 windows) - clearly bridging separate
wings, not one continuous run. Chaining is transitive (see
`components.connected_components`): two windows farther apart than this
threshold can still land in the same cluster through an intermediate
instance within range of both, so raising this constant grows clusters
along a whole run, not just any single pair.

The per-window exterior-sightline classification this category's earlier
version computed (does a 2D ray toward the nearest storey-footprint edge
clear the building, or re-enter it further out - see this module's
_classify_window docstring history for the fix that made it reliable) is
kept, not discarded: each cluster's evidence reports how many of its
windows are clear/self-obstructed/interior-facing, since that's exactly
what "how much real daylight does this cluster deliver" needs. Reuses
extractor.py's extract_envelope_shapes() extraction (info_envelope_shapes,
the same key envelope.py already declares) - no new extraction code
needed.
"""

import math
from collections import defaultdict

import ifcopenshell.util.element
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from ifc_units import length_scale, placement_xy

from ..components import connected_components
from ..footprints import info_polygon
from ..intent import make_member, make_intent

DEFAULT_GAP_TOLERANCE_M = 0.6
# Unlike DEFAULT_CLUSTER_DISTANCE_M below, this one is NOT backed by a clean
# empirical gap - measured window-to-nearest-footprint-edge offsets on
# data/test_5.ifc form a continuum (0.41m up to 12.09m, filling in
# gradually), since that distance genuinely varies continuously with wall
# thickness/reveal depth. 2.0m is a judgment call (generous for a thick
# wall + deep reveal, without drifting into "clearly somewhere else in the
# room") - confirmed only to fix a concrete misclassification bug (real
# exterior windows at 0.99m-1.42m were wrongly read as interior-facing by
# an earlier, cruder version of this same check), not to be the
# statistically "correct" cutoff.
DEFAULT_MAX_WALL_OFFSET_M = 2.0
DEFAULT_NEAR_ZONE_TOLERANCE_M = 0.5
DEFAULT_CLUSTER_DISTANCE_M = 7.0
DEFAULT_MIN_CLUSTER_SIZE = 2

VERDICT_TEXT = {
    "clear": "clear exterior view",
    "self_obstructed": "facing the building's own massing (a courtyard or re-entrant corner)",
    "no_exterior_direction": "interior/borrowed-light (no nearby exterior boundary)",
    "unknown": "unresolvable storey footprint",
}


def _storey_footprint(infos, gap_tolerance_m):
    """One combined footprint polygon (or MultiPolygon, if this storey
    genuinely has more than one disjoint block) for every slab at one
    storey. Same buffer-out/union/buffer-in closing envelope.py uses, and
    for the same reason: real adjacent floor panels routinely do NOT share
    an exact boundary (confirmed on data/test_5.ifc: 0.25m-0.5m real gaps
    between structural bay panels)."""
    polygons = [poly for info in infos for poly in [info_polygon(info)] if poly is not None]
    if not polygons:
        return None
    return unary_union([p.buffer(gap_tolerance_m) for p in polygons]).buffer(-gap_tolerance_m)


def _classify_window(x, y, footprint, max_wall_offset_m, near_zone_m):
    """Direction toward the window's nearest storey-footprint boundary
    point (not the host wall's own orientation - an earlier version tried
    that plus a fixed-distance probe and was confirmed wrong: several real
    exterior windows landed almost exactly on the probe distance, where
    floating-point/buffer-smoothing noise made the inside/outside test
    unreliable, and near a corner the true nearest edge isn't necessarily
    along the wall's own face-normal at all)."""
    point = Point(x, y)
    boundary = footprint.boundary
    nearest = boundary.interpolate(boundary.project(point))
    offset = point.distance(nearest)
    if offset > max_wall_offset_m:
        return "no_exterior_direction"

    dx, dy = nearest.x - x, nearest.y - y
    length = math.hypot(dx, dy)
    if length == 0:
        return "clear"
    dx, dy = dx / length, dy / length

    min_x, min_y, max_x, max_y = footprint.bounds
    ray_length_m = math.hypot(max_x - min_x, max_y - min_y) * 1.5
    start_m = offset + near_zone_m

    far_ray = LineString([
        (x + dx * start_m, y + dy * start_m),
        (x + dx * ray_length_m, y + dy * ray_length_m),
    ])
    return "self_obstructed" if far_ray.intersects(footprint) else "clear"


def _window_type(window):
    """(type key, display name) - IfcRelDefinesByType's own target, via
    ifcopenshell.util.element.get_type(). None-keyed (grouped together as
    "Untyped") if the window has no type relation at all - not split per
    window, since there is no better identity to group untyped windows by."""
    wtype = ifcopenshell.util.element.get_type(window)
    if wtype is None:
        return None, "Untyped"
    return wtype.GlobalId, (wtype.Name or wtype.GlobalId)


def detect(model, extracted, file_key,
           gap_tolerance_m=DEFAULT_GAP_TOLERANCE_M,
           max_wall_offset_m=DEFAULT_MAX_WALL_OFFSET_M,
           near_zone_m=DEFAULT_NEAR_ZONE_TOLERANCE_M,
           cluster_distance_m=DEFAULT_CLUSTER_DISTANCE_M,
           min_cluster_size=DEFAULT_MIN_CLUSTER_SIZE):
    windows = model.by_type("IfcWindow")
    if not windows:
        return []

    slab_infos = [info for info in ((extracted or {}).get("info_envelope_shapes") or []) if info["source"] == "IfcSlab"]
    by_storey = defaultdict(list)
    for info in slab_infos:
        element = model.by_guid(info["id"])
        storey = element and ifcopenshell.util.element.get_container(element, ifc_class="IfcBuildingStorey")
        if storey is not None:
            by_storey[storey.GlobalId].append(info)
    footprints_by_storey = {guid: _storey_footprint(infos, gap_tolerance_m) for guid, infos in by_storey.items()}

    # Placements in metres whatever the file's unit (docs/detectors.md rule 13). A
    # window without a placement is skipped: get_local_placement(None) is the
    # identity matrix, and four such windows once formed a phantom cluster at
    # (0, 0).
    scale = length_scale(model)
    window_data = {}
    type_names = {}
    by_type = defaultdict(list)
    for window in windows:
        xy = placement_xy(window, scale)
        if xy is None:
            continue
        x, y = xy
        type_guid, type_name = _window_type(window)
        type_names[type_guid] = type_name

        storey = ifcopenshell.util.element.get_container(window, ifc_class="IfcBuildingStorey")
        storey_guid = storey.GlobalId if storey is not None else None
        storey_name = (storey.Name or storey.GlobalId) if storey is not None else None

        footprint = footprints_by_storey.get(storey_guid) if storey_guid else None
        verdict = _classify_window(x, y, footprint, max_wall_offset_m, near_zone_m) if footprint is not None else "unknown"

        window_data[window.GlobalId] = {
            "x": x, "y": y, "storey_guid": storey_guid, "storey_name": storey_name, "verdict": verdict,
        }
        by_type[type_guid].append(window.GlobalId)

    intents = []
    for type_guid, guids in by_type.items():
        type_name = type_names[type_guid]

        edges = []
        for i in range(len(guids)):
            xi, yi = window_data[guids[i]]["x"], window_data[guids[i]]["y"]
            for j in range(i + 1, len(guids)):
                xj, yj = window_data[guids[j]]["x"], window_data[guids[j]]["y"]
                if math.hypot(xi - xj, yi - yj) <= cluster_distance_m:
                    edges.append((guids[i], guids[j]))

        for cluster_ids in connected_components(edges):
            if len(cluster_ids) < min_cluster_size:
                continue

            storey_names = sorted({window_data[guid]["storey_name"] for guid in cluster_ids if window_data[guid]["storey_name"]})
            storey_guids = sorted({window_data[guid]["storey_guid"] for guid in cluster_ids if window_data[guid]["storey_guid"]})
            verdict_counts = defaultdict(int)
            for guid in cluster_ids:
                verdict_counts[window_data[guid]["verdict"]] += 1
            verdict_summary = ", ".join(f"{count} {VERDICT_TEXT[verdict]}" for verdict, count in sorted(verdict_counts.items()))
            sorted_ids = sorted(cluster_ids)

            intents.append(make_intent(
                intent_id=f"{file_key}-lighting-{type_guid or 'untyped'}-" + "-".join(sorted_ids),
                intent_type="window_lighting_cluster",
                label=f"Lighting cluster: {type_name} ({len(cluster_ids)} windows, {len(storey_names)} storeys)",
                members=[make_member(guid, role="member", ifc_class="IfcWindow") for guid in sorted_ids],
                detector="lighting_clusters",
                rule="window_type_proximity_cluster",
                summary=(
                    f"{len(cluster_ids)} '{type_name}' windows sit within {cluster_distance_m:.0f}m of each "
                    f"other, spanning {len(storey_names)} storey(s) ({', '.join(storey_names)}) - {verdict_summary}."
                ),
                related_guids=storey_guids,
                metrics={
                    "typeName": type_name,
                    "windowCount": len(cluster_ids),
                    "storeys": storey_names,
                    "verdictCounts": dict(verdict_counts),
                    "clusterDistanceM": cluster_distance_m,
                },
            ))
    return intents
