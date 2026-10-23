"""The generic families. Every rule binding names one; the stubs keep a
rule `deferred` (rules.py refuses a bound rule of a stub family through
`available`) until the family is built."""

from . import adjacency, aggregate, measure, provision, route, stub

FAMILIES = {
    "measure": measure.run,
    "provision": provision.run,
    "route": route.run,
    "adjacency": adjacency.run,
    "aggregate": aggregate.run,
    "composition": stub.run,
    "footprint": stub.run,
    "classify": stub.run,
}
BUILT = ("measure", "provision", "route", "adjacency", "aggregate")
