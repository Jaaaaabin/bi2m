"""Room Access: the storey's rooms-and-doors readings as one category
(2026-10-08).

Three rules over the same rooms, formerly three categories: space_access
(reachable groups, isolated rooms, door anomalies, storeys without rooms),
space_syntax (the storey's most integrated room and its rings) and
circulation_horizontal (circulation spaces by name). Measured on the 23
local shards before the merge: every record of space_syntax and
circulation_horizontal had its members inside space_access's, so a reviewer
met the same rooms in three sections. The records are unchanged (ids,
types, rules, metrics); only provenance.detector reads "room_access".

Signals: IfcSpace, what none of the three can fire without
(circulation_horizontal needs no doors; the other two build the door graph
and return nothing without doors).
"""

from . import circulation_horizontal, space_access, space_syntax
from .merged import run_parts

ID = "room_access"
PARTS = (space_access, space_syntax, circulation_horizontal)


def detect(model, extracted, file_key, graph=None):
    return run_parts(ID, PARTS, model, extracted, file_key, graph=graph)
