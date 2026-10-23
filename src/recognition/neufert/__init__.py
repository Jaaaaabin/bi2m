"""Neufert K-rules as bi2m intent categories (2026-10-18;
docs/detectors.md "The 13 Neufert categories").

A K-rule is data: a population selector, named measures and the card's
op/threshold block (config/neufert/rules/<KID>.yaml, copied unchanged from
neufert_logic.md, plus config/neufert/bindings.yaml). A few generic family
modules run every rule bound to them; a Topic category is a label plus the
rules that carry that Topic. No module here knows a K-number.
"""
