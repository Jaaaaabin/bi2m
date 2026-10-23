"""Which models could which categories even run on? Eligibility only - this
script never runs a detector and never writes a shard.

It applies exactly the criteria `src/recognition/preflight.py` already uses
per model: every registry entry may declare `signals`,
the model-level facts its detector needs, and a category whose signal is
absent cannot produce output. Here those same signals are evaluated across a
whole library, so a corpus can be triaged BEFORE spending hours of
recognition on it (the corpus is the binding constraint; docs/roadmap.md
"Not built yet").

    uv run python scripts/eligibility_survey.py $BI2M_IFC_ROOT
    uv run python scripts/eligibility_survey.py data --verify 5   # cross-check
    uv run python scripts/eligibility_survey.py <dir> --json out.json

Why it does not use ifcopenshell for the survey itself. `ifcopenshell.open()`
parses the entire STEP file into an entity graph - seconds to minutes for the
20-120MB files this is meant to triage, so a 1240-file library would take
hours. Every signal in the grammar is answerable from the raw bytes instead:
"is there at least one instance of class X" is "does the token `IFCX(` occur",
and "is there a property named P with a value" is one anchored regex. That
turns the survey into a single sequential read, which is what the disk can do
fastest. Subtypes are NOT guessed - `by_type` includes them, so the token set
for each class is its subtype closure taken from the real schema
(`schema_by_name(...).declaration_by_name(...).subtypes()`), resolved per
file against that file's own FILE_SCHEMA.

--verify re-runs the authoritative `preflight.preflight()` through
ifcopenshell on a sample and diffs the two answers signal by signal. Run it
whenever the grammar or an exporter changes; a byte scan is a model of the
parse, and a model that is never checked against the thing it models is a
guess.
"""

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
from ifcopenshell import ifcopenshell_wrapper  # noqa: E402

from recognition import preflight as preflight_mod  # noqa: E402
from recognition.registry import CATEGORIES  # noqa: E402

CHUNK = 8 << 20
HEADER_BYTES = 8192
SCHEMA_RE = re.compile(rb"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", re.IGNORECASE)
# STEP writers differ on spacing after "=" (Revit writes "#13=IFCWALL(",
# Geometry Gym writes "#13= IFCWALL(") - so the token is anchored on the
# trailing "(" only, which is enough: no other entity name ends in one of
# these names, and a bare name never appears before "(" inside a string.
PROP_VALUE_RE = {}


def prop_regex(name):
    if name not in PROP_VALUE_RE:
        PROP_VALUE_RE[name] = re.compile(
            rb"IFCPROPERTYSINGLEVALUE\('" + re.escape(name.encode()) + rb"',[^,]*,([^,]{0,48})")
    return PROP_VALUE_RE[name]


def value_is_present(raw):
    """Mirrors preflight._property_present's acceptance: a NominalValue that
    is not $ and not an empty wrapped string. (.F. counts - "not external" is
    a stated fact, and the module says so explicitly for IsExternal.)"""
    raw = raw.strip()
    if not raw or raw.startswith(b"$"):
        return False
    return b"('')" not in raw and not raw.endswith(b"''")


# Schemas ifcopenshell cannot load at all (IFC2X2_FINAL, found 2026-09-22 in
# older third-party exports). Without a fallback every class
# probe silently reads "absent" and the file scores 1-2 eligible categories
# while plainly containing 19 product classes. IFC2X2's element taxonomy is a
# subset of IFC2X3's for everything the signal grammar names, so resolving
# subtypes against IFC2X3 is right where it matters and conservative where it
# is not: a class IFC2X2 lacks simply never appears in the bytes.
SCHEMA_FALLBACK = "IFC2X3"
unresolved_schemas = set()


def class_tokens(schema_name, ifc_class):
    """`by_type` includes subtypes, so the token set for a class is its whole
    subtype closure in THAT file's schema. An IFC4-only class asked of an
    IFC2X3 file simply has no declaration - absent, exactly as
    preflight._class_present treats the RuntimeError."""
    try:
        schema = ifcopenshell_wrapper.schema_by_name(schema_name)
    except Exception:
        unresolved_schemas.add(schema_name)
        try:
            schema = ifcopenshell_wrapper.schema_by_name(SCHEMA_FALLBACK)
        except Exception:
            return ()
    try:
        decl = schema.declaration_by_name(ifc_class)
    except Exception:
        return ()
    names, stack = set(), [decl]
    while stack:
        d = stack.pop()
        names.add(d.name().upper())
        try:
            stack.extend(d.subtypes())
        except Exception:
            pass
    return tuple(f"{n}(".encode() for n in sorted(names))


def needed_signals():
    return sorted({sig for info in CATEGORIES.values() for sig in info.get("signals", ())})


def read_schema(path):
    with open(path, "rb") as fh:
        head = fh.read(HEADER_BYTES)
    m = SCHEMA_RE.search(head)
    return m.group(1).decode("latin-1").upper() if m else "UNKNOWN"


def scan_file(path, signals, stop_early=True):
    """One sequential pass. Returns {signal: bool}. Tokens are dropped from
    the active set as soon as they are seen, and the read stops once every
    signal is decided - so a complete model costs a few MB and only a model
    MISSING something pays for the whole file."""
    schema = read_schema(path)
    classes, props = {}, {}
    for sig in signals:
        if sig.startswith(preflight_mod.PROP_PREFIX):
            props[sig] = sig[len(preflight_mod.PROP_PREFIX):]
        else:
            classes[sig] = [tok for cls in sig.split("|") for tok in class_tokens(schema, cls)]

    found = {sig: False for sig in signals}
    # A signal whose classes have no declaration in THIS file's schema keeps
    # its False and is never searched for - the same answer
    # preflight._class_present gives when by_type raises for an unknown class.
    pending_classes = {s: list(t) for s, t in classes.items() if t}
    pending_props = dict(props)
    longest = max((len(t) for toks in classes.values() for t in toks), default=32)
    tail = b""
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            buf = tail + chunk
            for sig in list(pending_classes):
                for tok in pending_classes[sig]:
                    if tok in buf:
                        found[sig] = True
                        del pending_classes[sig]
                        break
            for sig in list(pending_props):
                for m in prop_regex(pending_props[sig]).finditer(buf):
                    if value_is_present(m.group(1)):
                        found[sig] = True
                        del pending_props[sig]
                        break
            if stop_early and not pending_classes and not pending_props:
                break
            tail = buf[-(longest - 1):] if longest > 1 else b""
    return schema, found


def eligibility(found):
    eligible, blocked = [], {}
    for cid, info in CATEGORIES.items():
        missing = [s for s in info.get("signals", ()) if not found.get(s, False)]
        if missing:
            blocked[cid] = missing
        else:
            eligible.append(cid)
    return eligible, blocked


def verify(paths, signals):
    """Authoritative re-check through ifcopenshell on a sample."""
    print(f"\n=== verify: byte scan vs ifcopenshell preflight() on {len(paths)} file(s) ===")
    bad = 0
    for path in paths:
        schema, scanned = scan_file(path, signals, stop_early=False)
        model = ifcopenshell.open(str(path))
        truth = {sig: preflight_mod.signal_available(model, sig) for sig in signals}
        diff = {s: (scanned[s], truth[s]) for s in signals if scanned[s] != truth[s]}
        bad += bool(diff)
        status = "OK " if not diff else "DIFF"
        print(f"  [{status}] {path.name:28s} {schema:7s} "
              + ("all %d signals agree" % len(signals) if not diff
                 else "; ".join(f"{s}: scan={a} truth={b}" for s, (a, b) in diff.items())))
        del model
    print(f"  {len(paths) - bad}/{len(paths)} files agree on every signal")
    return bad == 0


def main():
    ap = argparse.ArgumentParser(description="Category eligibility across an IFC library (no computation).")
    ap.add_argument("target", help="Directory to walk, or a single .ifc file.")
    ap.add_argument("--json", help="Write the full per-model result here.")
    ap.add_argument("--limit", type=int, help="Only look at the first N files (by name).")
    ap.add_argument("--verify", type=int, default=0, help="Cross-check N sampled files against ifcopenshell.")
    ap.add_argument("--counts", action="store_true", help="Disable early exit (full read per file).")
    args = ap.parse_args()

    target = Path(args.target)
    paths = sorted(target.rglob("*.ifc")) if target.is_dir() else [target]
    if args.limit:
        paths = paths[:args.limit]
    if not paths:
        sys.exit(f"No .ifc files under {target}")

    signals = needed_signals()
    print(f"{len(paths)} model(s), {sum(p.stat().st_size for p in paths) / 2**30:.1f} GiB")
    print(f"{len(CATEGORIES)} categories, {len(signals)} distinct signals: {', '.join(signals)}")

    if args.verify:
        step = max(1, len(paths) // args.verify)
        if not verify(paths[::step][:args.verify], signals):
            print("  byte scan disagrees with ifcopenshell - fix before trusting the survey below", file=sys.stderr)
            sys.exit(1)

    rows, t0 = [], time.time()
    eligible_count = Counter()
    signal_count = Counter()
    by_schema = Counter()
    combo = Counter()
    read_bytes = 0
    for i, path in enumerate(paths, 1):
        try:
            schema, found = scan_file(path, signals, stop_early=not args.counts)
        except OSError as err:
            print(f"  unreadable: {path} ({err})", file=sys.stderr)
            continue
        eligible, blocked = eligibility(found)
        by_schema[schema] += 1
        for sig, ok in found.items():
            signal_count[sig] += bool(ok)
        for cid in eligible:
            eligible_count[cid] += 1
        combo[len(eligible)] += 1
        read_bytes += path.stat().st_size
        rows.append({"file": str(path), "schema": schema, "signals": found,
                     "eligible": eligible, "blocked": {k: v for k, v in blocked.items()}})
        if i % 100 == 0 or i == len(paths):
            print(f"  ... {i}/{len(paths)} ({time.time() - t0:.0f}s)", flush=True)

    n = len(rows)
    print(f"\nScanned {n} models in {time.time() - t0:.0f}s\n")
    if unresolved_schemas:
        print(f"NOTE: {', '.join(sorted(unresolved_schemas))} not loadable by ifcopenshell - "
              f"subtypes resolved against {SCHEMA_FALLBACK} instead (see class_tokens).\n")
    print("| Schema | models |")
    print("|---|---:|")
    for s, c in by_schema.most_common():
        print(f"| {s} | {c} |")

    print("\n| Signal | models with it | % |")
    print("|---|---:|---:|")
    for sig in signals:
        c = signal_count[sig]
        print(f"| `{sig}` | {c} | {100 * c / n:.1f} |")

    print("\n| Category | eligible models | % | blocked by |")
    print("|---|---:|---:|---|")
    blocked_reasons = defaultdict(Counter)
    for row in rows:
        for cid, missing in row["blocked"].items():
            for sig in missing:
                blocked_reasons[cid][sig] += 1
    for cid, info in CATEGORIES.items():
        c = eligible_count[cid]
        why = ", ".join(f"{sig} ({cnt})" for sig, cnt in blocked_reasons[cid].most_common(2)) or "—"
        print(f"| `{cid}` | {c} | {100 * c / n:.1f} | {why} |")

    print("\n| Categories eligible | models |")
    print("|---|---:|")
    for k in sorted(combo, reverse=True):
        print(f"| {k} of {len(CATEGORIES)} | {combo[k]} |")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "target": str(target), "models": n, "categories": list(CATEGORIES),
            "signals": signals, "bySchema": dict(by_schema),
            "eligibleCount": dict(eligible_count), "rows": rows,
        }, indent=1))
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
