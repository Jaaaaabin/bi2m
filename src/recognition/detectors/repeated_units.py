"""Repeated Units: the building's recurring room groups as one category
(2026-10-08).

Two rules over the same door graph, formerly two categories: unit_typology
(room programs that recur, by room names) and unit_layout (door layouts
that recur, by graph isomorphism). Measured on the 23 local shards before
the merge: every unit_layout record had its members inside a space_access
record's and the two corroborated each other 20 times; inside one category
those links are no longer drawn, the records all stay. Only
provenance.detector reads "repeated_units".

Signals: IfcSpace and IfcDoor; units are components of the door graph.
"""

from . import unit_layout, unit_typology
from .merged import run_parts

ID = "repeated_units"
PARTS = (unit_typology, unit_layout)


def detect(model, extracted, file_key, graph=None):
    return run_parts(ID, PARTS, model, extracted, file_key, graph=graph)
