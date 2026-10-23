"""Per-model session: the facts that are a function of one model alone,
memoised once per model instead of once per reader (the efficiency
exploration of 2026-10-22).

This file is step 1 of that round: the registry and the property-set memo.
Measured before it, on data/example_autcon.ifc (776 products), one run called
ifcopenshell.util.element.get_psets 2,484 times for 568 distinct elements -
the 135 doors about eight times each, by convention_outlier, room_access,
thermal_envelope, egress_fire, two Neufert Topics and preflight - because
only the Neufert Context memoised, and only for itself. Later steps add the
storey views (room_graph.py / room_routes.py memoise on the graph instance),
the footprint kinds, the selector populations and `run()`.

How a reader reaches the session: NOT by a new parameter. `psets_of(element)`
looks the session up through `element.file`, which on ifcopenshell 0.8.5 IS
the opened model object (checked for by_type, by_guid and traversed entities,
and for in-memory `ifcopenshell.file` fixtures), so `properties.property_value`,
preflight's probes and the Context keep their signatures and get the memo.
An element without a `.file` (a fake in a verify script) is read directly.

Two registries, one rule each (engine.context_for's "only the current model"
rule, now in one place):
  - explicit: `ModelSession.of(model)` registers a session its owner closes
    (the CLI per file, a warm server per model key, a `with` block in a
    sweep); it is never evicted by another model.
  - implicit: `ModelSession.current(model)` for a model nobody opened
    explicitly makes one session and keeps it until a DIFFERENT model asks,
    which replaces it (dropped, not closed: a Context still holding it keeps
    working on its own memos).
Readers call `current(model)` per read and never cache the result, so a
replaced-and-recreated implicit session is simply found again. `forget(model)`
drops both entries for a model a test mutates after a read (a fixture that
gains a pset must not be answered from the memo).

Memo contract: keyed on (element.id(), psets_only, qtos_only, should_inherit,
verbose) - every argument of get_psets - so the three call shapes src/ uses
(element; element with qtos_only; wall) never answer for each other. The
value handed out is get_psets' own dict, unchanged and shared: callers must
not mutate it (none does, grepped on 2026-10-22; scripts/verify_session.py
checks the memo hands out one object; a read-only guard mode is step 3). A failure is never
memoised: get_psets' exception propagates to the caller each time, so
`properties.property_value` still fails the detector that asked (as today)
while `Context.psets` keeps catching it (as today). One assumption:
ifcopenshell does not reuse a STEP id within a model's lifetime.

Imports: nothing from `recognition` or `extraction` at module level, because
properties -> session -> registry would be a cycle.
"""

import ifcopenshell.util.element


class SessionClosed(RuntimeError):
    """A fact was asked of a session after close()."""


_EXPLICIT = {}  # id(model) -> ModelSession; the session holds the model strongly, so the id cannot be reused meanwhile
_IMPLICIT = None  # the one session for a model nobody opened explicitly


class ModelSession:
    def __init__(self, model, *, file_key=None, path=None):
        self.model = model
        self.file_key = file_key
        self.path = path
        self._psets = {}
        self._closed = False

    # ---- registry ----

    @classmethod
    def of(cls, model, *, file_key=None, path=None):
        """An explicit session for an already-open model; the caller closes it."""
        session = cls(model, file_key=file_key, path=path)
        _EXPLICIT[id(model)] = session
        return session

    @classmethod
    def current(cls, model):
        """The session for this model object: the explicit one if registered,
        else the implicit one (created on demand, replaced when another model asks)."""
        global _IMPLICIT
        explicit = _EXPLICIT.get(id(model))
        if explicit is not None and explicit.model is model:
            return explicit
        if _IMPLICIT is not None and _IMPLICIT.model is model:
            return _IMPLICIT
        _IMPLICIT = cls(model)
        return _IMPLICIT

    @classmethod
    def forget_implicit(cls, model):
        """Drop the implicit session if it is this model's. A fresh neufert
        Context calls this: the verify scripts build a fixture, read it through
        a Context, mutate the SAME file and read again through a new Context,
        which today starts with empty caches. An explicit session (the CLI's,
        a warm server's) is never dropped this way."""
        global _IMPLICIT
        if _IMPLICIT is not None and _IMPLICIT.model is model:
            _IMPLICIT = None

    @classmethod
    def forget(cls, model):
        """Drop every session of this model: for a fixture that is mutated after a read."""
        global _IMPLICIT
        explicit = _EXPLICIT.get(id(model))
        if explicit is not None and explicit.model is model:
            del _EXPLICIT[id(model)]
        if _IMPLICIT is not None and _IMPLICIT.model is model:
            _IMPLICIT = None

    def close(self):
        """Drop the memos and the registry entry; idempotent."""
        global _IMPLICIT
        if self._closed:
            return
        self._closed = True
        self._psets = {}
        if _EXPLICIT.get(id(self.model)) is self:
            del _EXPLICIT[id(self.model)]
        if _IMPLICIT is self:
            _IMPLICIT = None
        self.model = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    # ---- facts ----

    def psets(self, element, *, psets_only=False, qtos_only=False, should_inherit=True, verbose=False):
        """ifcopenshell.util.element.get_psets(element, ...) once per (element, arguments)."""
        if self._closed:
            raise SessionClosed("the model session is closed")
        key = (element.id(), psets_only, qtos_only, should_inherit, verbose)
        try:
            return self._psets[key]
        except KeyError:
            pass
        value = ifcopenshell.util.element.get_psets(
            element, psets_only=psets_only, qtos_only=qtos_only, should_inherit=should_inherit, verbose=verbose
        )
        self._psets[key] = value
        return value


def psets_of(element, **flags):
    """The property sets of `element` through its model's session when it has
    one to find (its `.file`), else straight from ifcopenshell: the one call
    every reader in src/recognition makes instead of get_psets."""
    model = getattr(element, "file", None)
    if model is None:
        return ifcopenshell.util.element.get_psets(element, **flags)
    return ModelSession.current(model).psets(element, **flags)
