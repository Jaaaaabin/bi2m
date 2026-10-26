"""Cross-model comparison - a PROTOTYPE for tier 7 of the granularity ladder
("comparing whole models against each other"), the one rung with no
coverage at all.

Why this is a script and not a detector in src/recognition/. Every category
in registry.py is invoked as `detect(model, extracted, file_key)` - it sees
exactly one model, by design, and writes into that model's own shard. A
tier-7 statement is inherently about a RELATION BETWEEN models, so it has
nowhere to live in that structure. Rather than distort the detector
contract, this stays a separate tool. If cross-model findings ever need to
reach the validation panel, the natural shape is one intent per model
naming its nearest sibling, and the signature code here is what would
produce it.

What it compares. Each model is reduced to a normalized profile vector over
two vocabularies:
  - `cls:<IfcClass>`  share of that class among the model's physical
    products (excluding spatial structure, annotations and grids - the same
    filter scripts/coverage_report.py uses)
  - `pat:<intentType>`  share of that intent type among everything the
    recognition pipeline found for the model
Similarity is the cosine between two profiles. The element half says what
the building is MADE of; the intent half says what was RECOGNIZED in it,
so two models score alike only if both their construction and their
recognized intent structure agree.

Ground truth this was validated against. data/test_1.ifc and
data/test_2.ifc are byte-identical (they share one content key), so
a correct metric must score them exactly 1.000 - it does. Beyond that
tautology the ordering is architecturally interpretable rather than
arbitrary:
    test_6 <-> test_5    0.849   both column-heavy, curtain-walled, heavily
                                 furnished mixed-use blocks
    test_4 <-> test_5    0.637
    test_7 <-> test_4  0.539   the two mullion/plate-dominated towers
    test_3 <-> everything <=0.593  the outlier, and correctly so: it is the
                                 only model with IfcRelSpaceBoundary, and
                                 has neither windows nor furniture

Known limits, since this is a prototype and not a finished detector:
  - The profile is compositional, not structural. Two buildings with the
    same element mix arranged completely differently score identically.
    A real drift/similarity measure would compare the access GRAPHS
    (TopologicPy's Graph.Compare/WLKernel are candidates for exactly this);
    that needs a graph kernel and is not attempted here.
  - It cannot do the thing tier 7 is actually most wanted for - as-designed
    vs as-built, or drift across revisions - because THIS CORPUS CONTAINS NO
    SUCH PAIR. Every projectGuid in data/ and data/uploads/ maps to exactly
    one distinct content key: the uploads are byte-identical re-uploads, not
    revisions. Verified directly before building this. A drift measure would
    have nothing to be tested against, so none is offered.

Usage:
    uv run python scripts/compare_models.py
    uv run python scripts/compare_models.py --json
"""

import argparse
import collections
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402

from file_identity import compute_content_key  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
INTENTS_DIR = REPO_ROOT / "viewer" / "public" / "res" / "intents"


def build_profile(ifc_path):
    """Normalized (element-class share, intent-type share) vector."""
    file_key = compute_content_key(str(ifc_path))
    model = ifcopenshell.open(str(ifc_path))

    products = [
        element for element in model.by_type("IfcProduct")
        if not element.is_a("IfcSpatialStructureElement")
        and not element.is_a("IfcAnnotation")
        and not element.is_a("IfcGrid")
    ]
    classes = collections.Counter(element.is_a() for element in products)
    total = sum(classes.values()) or 1
    profile = {f"cls:{name}": count / total for name, count in classes.items()}

    shard = INTENTS_DIR / f"{file_key}.json"
    intent_count = 0
    if shard.is_file():
        intents = json.loads(shard.read_text()).get("intents", [])
        intent_count = len(intents)
        types = collections.Counter(entry["type"] for entry in intents)
        denominator = sum(types.values()) or 1
        profile.update({f"pat:{name}": count / denominator for name, count in types.items()})

    return file_key, profile, len(products), intent_count


def cosine(left, right):
    keys = set(left) | set(right)
    numerator = sum(left.get(key, 0.0) * right.get(key, 0.0) for key in keys)
    left_norm = math.sqrt(sum(left.get(key, 0.0) ** 2 for key in keys))
    right_norm = math.sqrt(sum(right.get(key, 0.0) ** 2 for key in keys))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="Emit the matrix as JSON.")
    args = parser.parse_args()

    profiles = {}
    for path in sorted(DATA_DIR.glob("*.ifc")):
        name = path.stem
        file_key, profile, products, intents = build_profile(path)
        profiles[name] = {
            "key": file_key,
            "profile": profile,
            "products": products,
            "intents": intents,
        }
    if not profiles:
        raise SystemExit(f"No .ifc files under {DATA_DIR}")

    names = list(profiles)
    matrix = {
        a: {b: cosine(profiles[a]["profile"], profiles[b]["profile"]) for b in names}
        for a in names
    }

    if args.json:
        print(json.dumps({
            "models": {
                name: {
                    "key": info["key"],
                    "products": info["products"],
                    "intents": info["intents"],
                }
                for name, info in profiles.items()
            },
            "similarity": matrix,
        }, indent=2))
        return

    width = max(len(name) for name in names) + 2
    print("Cross-model similarity - cosine over (element-class + intent-type) profile\n")
    print(" " * width + "".join(f"{name[:9]:>10s}" for name in names))
    for a in names:
        print(f"{a:<{width}s}" + "".join(f"{matrix[a][b]:10.3f}" for b in names))

    print("\nNearest structural sibling (byte-identical twins excluded):")
    for a in names:
        best_name, best_score = None, -1.0
        for b in names:
            if b == a or profiles[b]["key"] == profiles[a]["key"]:
                continue
            if matrix[a][b] > best_score:
                best_name, best_score = b, matrix[a][b]
        if best_name is None:
            print(f"  {a:<{width}s} (no non-identical peer)")
        else:
            print(f"  {a:<{width}s} -> {best_name:<{width}s} {best_score:.3f}")

    twins = collections.defaultdict(list)
    for name, info in profiles.items():
        twins[info["key"]].append(name)
    duplicates = {key: group for key, group in twins.items() if len(group) > 1}
    if duplicates:
        print("\nByte-identical groups (these MUST score 1.000 - the metric's own check):")
        for key, group in duplicates.items():
            scores = {
                f"{a}~{b}": round(matrix[a][b], 6)
                for i, a in enumerate(group) for b in group[i + 1:]
            }
            status = "OK" if all(abs(v - 1.0) < 1e-9 for v in scores.values()) else "FAILED"
            print(f"  [{status}] {key}: {', '.join(group)} -> {scores}")


if __name__ == "__main__":
    main()
