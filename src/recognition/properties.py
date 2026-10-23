"""Property-set lookups, shared since 2026-10-09.

`property_value(element, names)` returns the first non-None value of any
property in `names`, across every property set on the element. Every set is
searched rather than one named set because the corpus spreads the same
fact over Pset_WallCommon, Pset_BeamCommon and Revit-authored sets such as
"Analytical Properties" or a localized "Dimensions". When two sets carry
the same name, the first in ifcopenshell's `get_psets` order wins; no
corpus model does this today.

`is_external(element)` is True only for a literal `IsExternal` True.

Used by `beam_framing`, `egress_access`, `egress_reachability`,
`space_syntax` and `thermal_envelope`. Not used by `fire_compartments`,
whose `_fire_rating` skips the "unrated" spellings and keeps searching, and
not by `convention_outlier` or preflight, which read properties their own
way on purpose.
"""

from .session import psets_of


def property_value(element, names):
    # Through the model session's memo (session.py, 2026-10-22): the same
    # get_psets, once per element per run instead of once per reader.
    for pset in psets_of(element).values():
        for key, value in pset.items():
            if key in names and value is not None:
                return value
    return None


def is_external(element):
    return property_value(element, ("IsExternal",)) is True
