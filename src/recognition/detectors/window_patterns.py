"""Window Stacks and Clusters: the building's window patterns as one
category (2026-10-08).

Two rules, formerly two categories: window_alignment (windows stacked at
one plan position across storeys, and interrupted bays) and
lighting_clusters (same-type windows clustered by proximity across floors).
Measured on the 23 local shards before the merge: 98 % of the stack
records had their members inside a cluster record, and the two categories
corroborated each other 248 times; inside one category those links are no
longer drawn, the records all stay. Only provenance.detector reads
"window_patterns".

Signals: IfcWindow. Extraction: info_envelope_shapes, which
lighting_clusters reads for its wall offsets.
"""

from . import lighting_clusters, window_alignment
from .merged import run_parts

ID = "window_patterns"
PARTS = (window_alignment, lighting_clusters)


def drop_clusters_equal_to_stacks(records):
    """A lighting cluster whose members are exactly one stack's says nothing
    the stack does not (72 of 155 clusters on the local shards,
    2026-10-09): it is not written; the stack's
    metrics note `alsoLightingCluster` and carry the cluster's window type,
    per-window verdicts and count as `cluster*`. Order of the rest unchanged."""
    stacks = {frozenset(m["guid"] for m in r["members"]): r for r in records if r["type"] == "window_vertical_alignment"}
    kept = []
    for record in records:
        if record["type"] == "window_lighting_cluster":
            twin = stacks.get(frozenset(m["guid"] for m in record["members"]))
            if twin is not None:
                # The cluster's own claims move onto the stack, so nothing is lost.
                twin["evidence"]["metrics"]["alsoLightingCluster"] = True
                for key, moved in (("typeName", "clusterTypeName"), ("verdictCounts", "clusterVerdictCounts"), ("windowCount", "clusterWindowCount")):
                    if key in record["evidence"]["metrics"]:
                        twin["evidence"]["metrics"][moved] = record["evidence"]["metrics"][key]
                continue
        kept.append(record)
    return kept


def detect(model, extracted, file_key, graph=None):
    return drop_clusters_equal_to_stacks(run_parts(ID, PARTS, model, extracted, file_key, graph=graph))
