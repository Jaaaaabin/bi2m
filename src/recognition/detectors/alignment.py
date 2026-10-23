"""Column alignment: rows of columns on one storey, and whether each row
continues through the building ("Column Alignment" in the panel).

A new, self-contained rule-based detector - deliberately NOT a port of
src/tempo/gridSystemGenerator.py's GridGenerator (2194 lines): that class
also does GA-driven grid *optimization* (still deliberately deferred) and
its own bokeh/selenium/cairosvg visualization pipeline, none of
which are even in pyproject.toml today (confirmed by inspection - it can't
currently run). This reimplements just the "columns sharing an axis
coordinate on one storey" rule, the intended starting detector.
Verified against data/test_3.ifc: it recovers the exact X ~= 31.679m
line res/intent_groups.json's hand-authored mock already describes (the
mock hand-picks 5 of the real 8 ground-floor members at that X - this
detector finds the true, complete group).

Needs real column locations, not raw ObjectPlacement - confirmed on
data/test_3.ifc that every IfcColumn's ObjectPlacement resolves to (0, 0, 0)
because the real offset lives in a mapped Body representation instead (the
same reason src/extraction/columns.py's _get_location_column() has a
mapped-representation branch). Reuses that already-solved extraction step
via `extracted["info_st_columns"]` rather than re-deriving placement math.

Two levels, one category (merged 2026-10-07; until then the second level was
the separate `grid_claims` category, "Column Alignment Continuity"):
  - a ROW: >= min_members columns on one storey sharing X or Y within
    tolerance_m (`alignment_column_group`);
  - a ROW CLAIM: the same row on >= 2 column-bearing storeys, positive when
    it is on every one of them (`grid_line_consistency`), negative when it is
    missing on some (`grid_line_gap`, naming those storeys). Its per-storey
    rows are its evidence (`metrics.storeyRows`), not records of their own.
Measured on the 22 local shards before the merge: 748 of the 921 row records
were restated by one of the 185 row claims, so a reviewer judged the same
columns twice. A row on one storey only is still a record of its own. The
type ids, rule names and the claims' `-gridline-` ids are those `grid_claims`
wrote, so stored claims keep their ids; the folded rows' ids are gone.

Columns at one plan position (`skipped_column_ids`). Two columns cannot
stand at the same plan position on one storey. Measured on the 23 local
models with an IFC (2026-10-07), it happens two ways:
  - at the origin: columns whose mapped offset the extraction could not
    resolve all land on (0, 0), 8 to 12 per storey in aff2ec9a... and
    b16a2e26..., with different heights - which made rows at X = 0.000 and
    Y = 0.000 and a 48-column "stack". Their positions are unknown, so every
    column of such a cluster is left out;
  - anywhere else: the model holds the same column twice or more (same type,
    same height, another element id - 250 copies in 4173e835..., 2 to 9 in
    four more models). The position is real, so one column is kept, the
    first by GUID, and the copies are left out.
A single column at the origin is kept: grid A/1 often sits there.
structural.py carries the same guard for its stacks.
"""

from collections import defaultdict

import ifcopenshell.util.element

from ..intent import make_member, make_intent

AXES = (("X", 0), ("Y", 1))
DEFAULT_TOLERANCE_M = 0.01
DEFAULT_MIN_MEMBERS = 3
# "The same plan position" for the guard: structural.py's column stack
# tolerance, so a position this detector distrusts is one structural would
# have stacked.
SAME_POSITION_M = 0.05


def _format_value(value):
    """31.679 -> "31679" (mirrors the mock fixture's id convention, e.g.
    "test_0-grid-x31679")."""
    return f"{value:.3f}".replace(".", "").replace("-", "n")


def skipped_column_ids(columns, get_storey, tolerance_m=SAME_POSITION_M):
    """GUIDs to leave out where several columns share a plan position on one
    storey: all of them at the origin, all but the first by GUID elsewhere
    (see the module docstring)."""
    by_position = defaultdict(list)
    for column in columns:
        storey = get_storey(column["id"])
        if storey is None:
            continue
        x, y = column["location"][0][0], column["location"][0][1]
        by_position[(storey.GlobalId, round(x / tolerance_m), round(y / tolerance_m))].append(column["id"])
    skipped = set()
    for (_storey, bx, by), guids in by_position.items():
        if len(guids) < 2:
            continue
        skipped.update(guids if (bx, by) == (0, 0) else sorted(guids)[1:])
    return skipped


def _storey_rows(model, columns, get_storey, tolerance_m, min_members):
    """Every row: {axis, value, storeyGuid, storeyName, members [(guid, coord)]},
    in the order the records have always been written in."""
    rows = []
    for axis_label, axis_index in AXES:
        # Bucket by (storey, rounded coordinate) - safe here since repeated
        # coordinates in real IFC exports cluster within ~1e-10m of each
        # other (floating-point noise only), well under any sane tolerance.
        groups = defaultdict(list)
        for column in columns:
            storey = get_storey(column["id"])
            if storey is None:
                continue
            coord = column["location"][0][axis_index]
            groups[(storey.GlobalId, round(coord / tolerance_m))].append((column["id"], coord))

        for (storey_guid, _bucket), members in groups.items():
            if len(members) < min_members:
                continue
            avg_value = sum(coord for _, coord in members) / len(members)
            storey = model.by_guid(storey_guid)
            rows.append({
                "axis": axis_label,
                "value": avg_value,
                "storeyGuid": storey_guid,
                "storeyName": storey.Name if storey and storey.Name else storey_guid,
                "members": members,
            })
    return rows


def _row_intent(row, file_key, tolerance_m):
    axis_label, avg_value, storey_guid, storey_name = row["axis"], row["value"], row["storeyGuid"], row["storeyName"]
    members = row["members"]
    return make_intent(
        intent_id=f"{file_key}-grid-{axis_label.lower()}{_format_value(avg_value)}-{storey_guid}",
        intent_type="alignment_column_group",
        label=f"Column alignment {axis_label} ≈ {avg_value:.3f}m on {storey_name} ({len(members)} columns)",
        members=[make_member(guid, ifc_class="IfcColumn") for guid, _ in members],
        detector="alignment",
        rule="column_axis_alignment",
        summary=(
            f"{len(members)} IfcColumn instances on storey {storey_guid} "
            f"({storey_name}) share {axis_label} ≈ {avg_value:.3f}m; no other "
            f"column-bearing storey has this row."
        ),
        related_guids=[storey_guid],
        metrics={
            "axis": axis_label,
            "value": round(avg_value, 3),
            "toleranceM": tolerance_m,
            "count": len(members),
            "storeyGuid": storey_guid,
        },
    )


def _row_claims(model, rows, column_storeys, file_key, tolerance_m):
    """Rows on >= 2 column-bearing storeys as one claim each. Returns
    (claims, ids of the rows folded into them). Formerly grid_claims.detect,
    unchanged in what it decides and in its ids."""
    storeys_sorted = sorted(model.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation)
    rank_of = {s.GlobalId: i for i, s in enumerate(storeys_sorted)}
    name_of = {s.GlobalId: (s.Name or s.GlobalId) for s in storeys_sorted}
    column_storeys = {g for g in column_storeys if g in rank_of}
    if len(column_storeys) < 2:
        return [], set()

    # (axis, bucket) -> {storey_guid: row}; the bucket is taken from the
    # row's rounded value, as grid_claims took it from the row record.
    lines = defaultdict(dict)
    for index, row in enumerate(rows):
        lines[(row["axis"], round(round(row["value"], 3) / tolerance_m))][row["storeyGuid"]] = index

    claims, folded = [], set()
    for (axis, _bucket), by_storey in sorted(lines.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if len(by_storey) < 2:
            continue
        folded.update(by_storey.values())
        values = [round(rows[i]["value"], 3) for i in by_storey.values()]
        avg_value = sum(values) / len(values)
        present = sorted(by_storey, key=lambda g: rank_of[g])
        missing = sorted(column_storeys - set(by_storey), key=lambda g: rank_of[g])
        member_pairs = sorted(
            (rank_of[storey_guid], guid) for storey_guid, i in by_storey.items() for guid, _ in rows[i]["members"]
        )
        members = [make_member(guid, ifc_class="IfcColumn") for _, guid in member_pairs]
        complete = not missing
        present_names = [name_of[g] for g in present]
        missing_names = [name_of[g] for g in missing]
        value_txt = f"{axis} ≈ {avg_value:.3f}m"

        claims.append(make_intent(
            intent_id=f"{file_key}-gridline-{axis.lower()}{_format_value(avg_value)}",
            intent_type="grid_line_consistency" if complete else "grid_line_gap",
            label=(
                f"Column alignment {value_txt} continues through all {len(present)} storeys"
                if complete else
                f"Column alignment {value_txt} breaks on {', '.join(missing_names)} ({len(present)} of {len(column_storeys)} storeys)"
            ),
            members=members,
            detector="alignment",
            rule="grid_line_universal" if complete else "grid_line_universal_violated",
            summary=(
                f"{len(members)} IfcColumn instances share {value_txt} on every column-bearing storey "
                f"({', '.join(present_names)}) - the column alignment continues through the building."
                if complete else
                f"{len(members)} IfcColumn instances share {value_txt} on {', '.join(present_names)}, "
                f"but no column sits on that line on {', '.join(missing_names)} - the column alignment is not carried "
                f"through every storey."
            ),
            related_guids=present + missing,
            metrics={
                "axis": axis, "value": round(avg_value, 3), "toleranceM": tolerance_m,
                "storeysPresent": present_names, "storeysMissing": missing_names,
                "columnCount": len(members), "instanceRecordsCollapsed": len(by_storey),
                "storeyRows": [
                    {"storey": name_of[g], "storeyGuid": g, "value": round(rows[by_storey[g]]["value"], 3),
                     "count": len(rows[by_storey[g]]["members"])}
                    for g in present
                ],
            },
            polarity="positive" if complete else "negative",
        ))
    return claims, folded


def detect(model, extracted, file_key, tolerance_m=DEFAULT_TOLERANCE_M, min_members=DEFAULT_MIN_MEMBERS):
    columns = (extracted or {}).get("info_st_columns", [])
    if not columns:
        return []

    storey_cache = {}

    def get_storey(guid):
        if guid not in storey_cache:
            element = model.by_guid(guid)
            storey_cache[guid] = (
                ifcopenshell.util.element.get_container(element, ifc_class="IfcBuildingStorey")
                if element else None
            )
        return storey_cache[guid]

    skipped = skipped_column_ids(columns, get_storey)
    columns = [c for c in columns if c["id"] not in skipped]

    rows = _storey_rows(model, columns, get_storey, tolerance_m, min_members)
    # Storeys that carry columns at all - the universe a row claim quantifies over.
    column_storeys = {get_storey(c["id"]).GlobalId for c in columns if get_storey(c["id"]) is not None}
    claims, folded = _row_claims(model, rows, column_storeys, file_key, tolerance_m)
    singles = [_row_intent(row, file_key, tolerance_m) for i, row in enumerate(rows) if i not in folded]
    return singles + claims
