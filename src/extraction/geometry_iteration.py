"""Shared ifcopenshell.geom.iterator helper.

Consolidates the 6 near-identical iterator loops that used to be duplicated across
floor/wall/column/curtain-wall-member/curtain-wall-plate extraction, each of which
spun up its own multiprocessing pool over a disjoint element subset. Callers should
prefer combining multiple element-type subsets into one `elements` list where the
call site allows it, to cut pool spin-up overhead further.
"""

import multiprocessing

import ifcopenshell.geom


def iterate_shapes(settings, model, elements, type_geo):
    """Yield each shape from an ifcopenshell.geom.iterator over `elements`.

    No-op (yields nothing) unless type_geo == 'triangle' and elements is non-empty,
    matching the original per-callsite guards.
    """
    if type_geo != "triangle" or not elements:
        return

    iterator = ifcopenshell.geom.iterator(
        settings, model, multiprocessing.cpu_count(), include=elements
    )

    if not iterator.initialize():
        return

    # Streaming on purpose: get() hands back a view into a buffer that the
    # next() call reuses, so shapes must be consumed before advancing -
    # buffering them for a sort produced empty geometry and a segfault
    # (tried 2026-09-19). Worker completion order is therefore NOT
    # deterministic here; consumers that need a stable order sort the small
    # info dicts they build from these shapes (see recognize_intents.py's
    # build_extracted), not the shapes themselves.
    while True:
        yield iterator.get()
        if not iterator.next():
            break
