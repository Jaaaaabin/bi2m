"""Egress and Fire: the storey's regulatory door readings as one category
(2026-10-08).

Three rules, formerly three categories: egress_reachability (rooms that
reach an external door, and those that do not), egress_access (the external
doors themselves) and fire_compartments (the door graph cut at fire-rated
doors). Kept apart from room_access, although every egress_reachability
record's members lie inside a space_access record's: corroboration links
records of different categories only, and the 66 cross-checks between an
access group and its egress reading are worth keeping, as is the
regulatory section. The records are unchanged; only provenance.detector
reads "egress_fire".

Signals: IfcDoor, what none of the three can fire without.
"""

from . import egress_access, egress_reachability, fire_compartments
from .merged import run_parts

ID = "egress_fire"
PARTS = (egress_reachability, egress_access, fire_compartments)


def detect(model, extracted, file_key, graph=None):
    return run_parts(ID, PARTS, model, extracted, file_key, graph=graph)
