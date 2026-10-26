"""Our Neufert rules (rules/, branch zihan_dev1) as bi2m categories.

One category per design-decision topic (rules/decisions.json) that holds active rules (rules/_status.json); each runs
rules/bi2m_records.py, which evaluates the rules element by element on the graph we already extracted for this model
(runs/graphs/, found through the viewer library index) and returns one record per (rule, outcome): pass, fail,
unknown, scenario. Every record carries the rule's verbatim Neufert quote(s), its concrete IF and the measured values.

A model with no extracted graph (e.g. data/example_autcon.ifc, or a model outside the library) yields no records.
Records live in their own panel section "rules" (viewer/panels/intentPanel.js).
"""
import importlib.util
from pathlib import Path

from .intent import make_intent, make_member

_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("zr_bi2m_records", _REPO / "rules" / "bi2m_records.py")
BR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BR)

SECTION = BR.SECTION
TOPICS = BR.TOPICS          # [{category, did, label, level}]
intent_types = BR.intent_types


def detector(category_id):
    def detect(model, extracted, file_key, graph=None):
        raw = BR.records_for(file_key).get(category_id, [])
        return [
            make_intent(
                intent_id=r["intent_id"],
                intent_type=r["intent_type"],
                label=r["label"],
                members=[make_member(g, role=role, ifc_class=cls) for g, role, cls in r["members"]],
                detector=category_id,
                rule=r["rule"],
                summary=r["summary"],
                metrics=r["metrics"],
                polarity=r["polarity"],
            )
            for r in raw
        ]
    detect.__name__ = f"detect_{category_id}"
    detect.__doc__ = f"Our rules for decision topic {category_id} (rules/bi2m_records.py)."
    return detect
