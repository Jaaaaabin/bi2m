"""Floor-slab refinement: info_floors -> closed-loop refined slab outlines.

A distinct data product (info_floor_slabs / info_unique_floor_slabs) from raw
floors.py extraction - not more extraction, a post-processing stage.
"""

from collections import defaultdict

from shapely.geometry import Polygon

from toolsQuickUtils import find_closed_loops


def refine_slab_shapes_per_storey(info_floors, thin_slab_limit=0.05):
    """Group floor slabs by elevation, find closed loops per storey, and return
    them sorted by area with each area normalized against the largest loop."""

    storey_values = list(set(item["elevation"] for item in info_floors))
    slab_z_groups = defaultdict(list)
    segment_z_groups = defaultdict(list)

    for st_z in storey_values:
        slab_per_st_z = [
            slab for slab in info_floors
            if slab["elevation"] == st_z and slab["width"] > thin_slab_limit
        ]
        slab_z_groups[st_z] = slab_per_st_z

    for st_z, values in slab_z_groups.items():
        if len(values) > 1:
            segment_z_groups[st_z] = [value["location"] for value in values]
            segment_z_groups[st_z] = [item for sublist in segment_z_groups[st_z] for item in sublist]
        elif len(values) == 1:
            segment_z_groups[st_z] = values[0]["location"]
        else:
            return None

    max_area = 0
    floor_slab_closed_loops = []

    for st_z, segments in segment_z_groups.items():
        loops = find_closed_loops(segments)
        for loop in loops:
            polygon = Polygon(loop)
            area = polygon.area
            floor_slab_closed_loops.append((st_z, loop, area))
            if area > max_area:
                max_area = area

    floor_slab_closed_loops.sort(key=lambda x: x[2], reverse=True)
    return [(st_z, loop, area / max_area) for st_z, loop, area in floor_slab_closed_loops]


def _generate_point_pairs(points):
    point_pairs = []
    num_points = len(points)
    if num_points < 2:
        return point_pairs
    for i in range(num_points - 1):
        point_pairs.append((points[i], points[i + 1]))
    return point_pairs


def update_floor_with_refined_slabs(info_floors, info_floor_slabs, splitter_percent=0.8):
    """Keep only the dominant (large-area-ratio) refined slab loop per storey."""

    tempo_dict = defaultdict(dict)
    unique_slab_width = max(fl["width"] for fl in info_floors)

    for (v, segments, ratio) in info_floor_slabs:
        if ratio > splitter_percent:
            tempo_dict[v] = {
                "points": _generate_point_pairs(segments),
                "area_ratio": ratio,
                "width": unique_slab_width,
            }

    return tempo_dict


def refine_floor_slabs(info_floors, thin_slab_limit=0.05, splitter_percent=0.8):
    """Run the full refinement stage. Returns (info_floor_slabs, info_unique_floor_slabs)."""

    info_floor_slabs = refine_slab_shapes_per_storey(info_floors, thin_slab_limit=thin_slab_limit)
    info_unique_floor_slabs = update_floor_with_refined_slabs(
        info_floors, info_floor_slabs, splitter_percent=splitter_percent)
    return info_floor_slabs, info_unique_floor_slabs
