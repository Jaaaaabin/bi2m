"""Beam framing modules: load-bearing IfcBeam instances that share one span
on one storey - a repeated structural bay - with each module also reporting
how many storeys carry a module of that same span, i.e. whether the framing
repeats up the building.

Closes the largest single element-coverage gap this package had. Before this
module IfcBeam was 0 of 1163 covered corpus-wide, which is
an inconsistency inside the `structural` domain on its own terms:
structural.py models the columns and the load-bearing walls but nothing
spanning between them, so the load path was described only in its vertical
segments and never its horizontal ones.

Signal: `Pset_BeamCommon.Span` plus `Pset_BeamCommon.LoadBearing`, both
present on 100% of beams in every one of the 5 corpus models that have any
(data/test_2.ifc 85, data/test_6.ifc 85, data/test_4.ifc 548,
data/test_5.ifc 360, data/test_7.ifc 85; data/test_3.ifc has no beams at
all). Every beam in all five is LoadBearing=True, so that flag currently
filters nothing - it is checked anyway rather than assumed, since a
non-load-bearing trim//fascia beam in a future file should not be read as
part of a structural bay.

Deliberately NOT geometric, unlike every detector in this package except
thermal_envelope.py. Beam placement is degenerate in two of the five files
(`get_local_placement` resolves to (0, 0) for 548/548 beams in
data/test_4.ifc and 352/360 in data/test_5.ifc - the same mapped-
representation quirk extraction/columns.py's `_get_location_column` already
works around for columns), and the `Axis` representation, which would have
given a centreline direction directly, is not a plain IfcPolyline in ANY of
the five (0 usable out of 1163 - the items are mapped/trimmed curves).
Rather than port the column workaround to a third element type for a
signal the model already states outright, this reads the declared span. A
framing-DIRECTION detector (which way the bay spans) is the natural
follow-up and does need that geometry work; it is not attempted here.

Spans are normalized to metres via `ifcopenshell.util.unit.calculate_unit_
scale` - required, not cosmetic: data/test_6.ifc authors its spans in
millimetres (60000.0 where the other four write 5.0-66.0), so grouping on
raw values is fine within one file but every reported number and the
cross-file tolerance would otherwise be meaningless.

What the corpus actually shows - a real, and quite strong, repeated-bay
intent in every file: data/test_4.ifc has 214 beams at a 7.0m span, 140 at
6.0m and 96 at 5.0m; data/test_5.ifc carries exactly 90 beams on each of 4
storeys, its span groups falling in exact multiples of 24;
data/test_2.ifc has exactly 17 beams on each of 5 storeys. That
per-storey regularity is the "each typical floor repeats the same framing"
intent at tier 6 of the granularity ladder, and the `storeyRecurrence` metric
below is what makes it checkable rather than merely visible.

Taxonomically this is also the package's first tier-3 (local motif /
typology) statement on the granularity ladder, previously empty: a module
is defined by a shared property value across an unordered set, not by where
its members sit, so it recognizes a repeated bay wherever it occurs rather
than only where coordinates line up. The same gap existed on
the quantifier axis - `storeyRecurrence` is a type-level claim about the
building, not another instance-level record.
"""

from collections import defaultdict

import ifcopenshell.util.element
import ifcopenshell.util.unit

from ..intent import make_member, make_intent
from ..properties import property_value
from ..storeys import get_storey

# Two beams count as the same bay if their spans agree to this many metres.
# Deliberately tight: the corpus's own span values are authored as round
# numbers (5.0/6.0/7.0/10.0 in data/test_4.ifc) or repeat exactly
# (data/test_5.ifc), so anything looser would merge genuinely different
# bays rather than absorb noise.
DEFAULT_SPAN_TOLERANCE_M = 0.05
DEFAULT_MIN_MEMBERS = 3


def detect(model, extracted, file_key,
           span_tolerance_m=DEFAULT_SPAN_TOLERANCE_M, min_members=DEFAULT_MIN_MEMBERS):
    try:
        beams = model.by_type("IfcBeam")
    except RuntimeError:
        return []
    if not beams:
        return []

    unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

    # (storey guid, span bucket) -> [(beam, span in metres)]
    groups = defaultdict(list)
    for beam in beams:
        if property_value(beam, ("LoadBearing",)) is not True:
            continue
        raw_span = property_value(beam, ("Span",))
        if not isinstance(raw_span, (int, float)) or raw_span <= 0:
            continue
        span_m = float(raw_span) * unit_scale
        storey = get_storey(beam)
        if storey is None:
            continue
        groups[(storey.GlobalId, round(span_m / span_tolerance_m))].append((beam, span_m))

    # How many distinct storeys carry a module at each span bucket - the
    # type-level "does this bay repeat up the building" claim.
    storeys_per_bucket = defaultdict(set)
    for (storey_guid, bucket), members in groups.items():
        if len(members) >= min_members:
            storeys_per_bucket[bucket].add(storey_guid)

    intents = []
    for (storey_guid, bucket), members in groups.items():
        if len(members) < min_members:
            continue

        mean_span = sum(span for _, span in members) / len(members)
        storey = model.by_guid(storey_guid)
        storey_name = storey.Name if storey and storey.Name else storey_guid
        recurrence = len(storeys_per_bucket[bucket])

        repeat_note = (
            f" The same {mean_span:.2f}m bay recurs on {recurrence} storeys."
            if recurrence > 1 else
            f" No other storey carries a {mean_span:.2f}m bay."
        )
        intents.append(make_intent(
            intent_id=f"{file_key}-beambay-{bucket}-{storey_guid}",
            intent_type="beam_framing_module",
            label=(
                f"Framing bay {mean_span:.2f}m x{len(members)} ({storey_name})"
                + (f", repeats on {recurrence} storeys" if recurrence > 1 else "")
            ),
            members=[make_member(beam.GlobalId, ifc_class=beam.is_a()) for beam, _ in members],
            detector="beam_framing",
            rule="beam_span_module",
            summary=(
                f"{len(members)} load-bearing IfcBeam instances on storey "
                f"{storey_name} share a declared span of {mean_span:.2f}m "
                f"(+/- {span_tolerance_m}m), forming one repeated structural "
                f"bay.{repeat_note}"
            ),
            related_guids=[storey_guid],
            metrics={
                "spanM": round(mean_span, 3),
                "count": len(members),
                "storey": storey_name,
                "storeyRecurrence": recurrence,
                "spanToleranceM": span_tolerance_m,
            },
        ))

    return intents
