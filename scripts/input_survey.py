"""Input survey: what each IFC file actually offers the detectors, counted
at the byte level in one pass per file - no ifcopenshell, no geometry.

Goes one level below scripts/eligibility_survey.py, which answers "is the
signal present at all?". This answers the questions the detectors really
ask: how many storeys, how many spaces carry a name and in which language,
how many IsExternal values are True rather than merely present, how many
space boundaries are physical, whether placements exist, and which length
unit the file is authored in (every geometric threshold in the package is
written in metres).

    uv run python scripts/input_survey.py $BI2M_IFC_ROOT --json out.json
    uv run python scripts/input_survey.py data/test_3.ifc data/test_5.ifc

Each row is one file. Property VALUE counts are lower bounds: IFC4 Revit
exports share one IFCPROPERTYSINGLEVALUE instance between every property set
that carries the same value, so "IsExternal true=1" means "at least one
element", not "one element". Presence of a value is reliable; its count is
not, and which CLASS carries it cannot be read at the byte level at all. Entity counts use the
opening token `IFCXXX(` so subtypes are counted under their own name
(IFCWALLSTANDARDCASE is not folded into IFCWALL here).
"""

import argparse
import collections
import json
import mmap
import os
import re
import sys
import time

ENTITY_TOKENS = (
    "IFCBUILDINGSTOREY", "IFCSPACE", "IFCDOOR", "IFCWINDOW", "IFCWALL", "IFCWALLSTANDARDCASE",
    "IFCCOLUMN", "IFCBEAM", "IFCSLAB", "IFCROOF", "IFCSTAIR", "IFCSTAIRFLIGHT", "IFCRAMP",
    "IFCRAMPFLIGHT", "IFCCURTAINWALL", "IFCMEMBER", "IFCPLATE", "IFCFURNISHINGELEMENT",
    "IFCFURNITURE", "IFCSYSTEMFURNITUREELEMENT", "IFCFLOWTERMINAL", "IFCSANITARYTERMINAL",
    "IFCBUILDINGELEMENTPROXY", "IFCTRANSPORTELEMENT", "IFCZONE", "IFCMAPPEDITEM",
    "IFCWINDOWTYPE", "IFCWINDOWSTYLE", "IFCDOORTYPE", "IFCDOORSTYLE", "IFCQUANTITYAREA",
    "IFCRELSPACEBOUNDARY", "IFCRELFILLSELEMENT", "IFCRELVOIDSELEMENT", "IFCRELAGGREGATES",
    "IFCRELDEFINESBYTYPE", "IFCRELCONTAINEDINSPATIALSTRUCTURE", "IFCRELCONNECTSPATHELEMENTS",
    "IFCRELASSIGNSTOGROUP", "IFCPROPERTYSINGLEVALUE", "IFCPROPERTYSET", "IFCELEMENTQUANTITY",
    "IFCGRID", "IFCGRIDAXIS", "IFCCLASSIFICATIONREFERENCE", "IFCRELASSOCIATESCLASSIFICATION",
    "IFCSPACETYPE", "IFCOPENINGELEMENT",
)
TOKEN_RE = re.compile(rb"=\s*(IFC[A-Z0-9]+)\(")
SCHEMA_RE = re.compile(rb"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'")
# The ASSIGNED length unit, resolved through IfcUnitAssignment: Revit files
# declare several SI length units (metre for derived units, plus the project
# unit), so "a millimetre unit exists somewhere" is not "the file is in
# millimetres". One centimetre model (pre-renumber private-corpus model 0060,
# removed from the corpus on 2026-09-23 and kept aside) declared
# metre, decimetre and centimetre and was authored in centimetres.
UNIT_ASSIGNMENT_RE = re.compile(rb"IFCUNITASSIGNMENT\(\(([^)]*)\)\)")
SI_LENGTH_RE = re.compile(rb"#(\d+)\s*=\s*IFCSIUNIT\(\*,\.LENGTHUNIT\.,(\$|\.[A-Z]+\.),\.METRE\.\)")
CONV_LENGTH_RE = re.compile(rb"#(\d+)\s*=\s*IFCCONVERSIONBASEDUNIT\([^,]*,\.LENGTHUNIT\.,'([^']*)'")
SI_PREFIX_SCALE = {b"$": 1.0, b".DECI.": 0.1, b".CENTI.": 0.01, b".MILLI.": 0.001, b".KILO.": 1000.0}


def resolve_length_unit(buf):
    """('mm' | 'cm' | 'dm' | 'm' | 'conv:<name>' | 'unknown', scale-to-metres or None)."""
    assigned = set()
    for m in UNIT_ASSIGNMENT_RE.finditer(buf):
        assigned.update(re.findall(rb"#(\d+)", m.group(1)))
    for eid, prefix in SI_LENGTH_RE.findall(buf):
        if eid in assigned:
            return {b"$": "m", b".DECI.": "dm", b".CENTI.": "cm", b".MILLI.": "mm"}.get(prefix, prefix.decode()), SI_PREFIX_SCALE.get(prefix)
    for eid, name in CONV_LENGTH_RE.findall(buf):
        if eid in assigned:
            return "conv:" + name.decode("latin-1"), None
    return "unknown", None
# IFCPROPERTYSINGLEVALUE(Name, Description, NominalValue, Unit)
PROP_RE = re.compile(
    rb"IFCPROPERTYSINGLEVALUE\('(IsExternal|LoadBearing|FireRating|Span|ThermalTransmittance|NetFloorArea|Reference)',"
    rb"[^,]*,(?:IFC[A-Z]+\(([^)]*)\)|\$)"
)
# IFCRELSPACEBOUNDARY(GlobalId, OwnerHistory, Name, Description, RelatingSpace, RelatedBuildingElement, ...)
BOUNDARY_RE = re.compile(rb"IFCRELSPACEBOUNDARY\((?:[^,]*,){5}(\$|#\d+),")
# IFCSPACE(GlobalId, OwnerHistory, Name, Description, ObjectType, ObjectPlacement, Representation, LongName, ...)
SPACE_RE = re.compile(rb"IFCSPACE\('[^']*',[^,]*,(\$|'[^']*'),[^,]*,[^,]*,(\$|#\d+),(\$|#\d+),(\$|'[^']*'),")
# IFCWINDOW / IFCDOOR (GlobalId, OwnerHistory, Name, Description, ObjectType, ObjectPlacement, Representation, Tag, OverallHeight, OverallWidth)
OPENING_RE = re.compile(rb"(IFCWINDOW|IFCDOOR)\('[^']*',[^,]*,(\$|'[^']*'),[^,]*,[^,]*,(\$|#\d+),(\$|#\d+),[^,]*,(\$|[-0-9.E+]+),(\$|[-0-9.E+]+)")
FLIGHT_RE = re.compile(rb"IFC(?:STAIR|RAMP)FLIGHT\('[^']*',[^,]*,[^,]*,[^,]*,[^,]*,(\$|#\d+),")
# Furniture-ish and sanitary-ish names: instance Name only (type names would need a second pass).
FIXTURE_RE = re.compile(rb"IFC(?:FURNISHINGELEMENT|FURNITURE|SYSTEMFURNITUREELEMENT|FLOWTERMINAL|SANITARYTERMINAL|BUILDINGELEMENTPROXY)\('[^']*',[^,]*,'([^']*)'")

# Name conventions the detectors key on (English, from the code) and the German
# equivalents this library is expected to carry (the private corpus is a German export set).
CIRC_H_EN = ("corridor", "hall", "lobby", "foyer", "vestibule", "passage", "aisle")
CIRC_H_DE = ("flur", "gang", "korridor", "halle", "diele", "vorraum", "eingang", "windfang", "erschlie")
CIRC_V_EN = ("stair", "elevator", "lift", "shaft", "escalator", "ramp")
CIRC_V_DE = ("treppe", "aufzug", "fahrstuhl", "schacht", "rampe")
SEAT_EN = ("chair", "seat", "stool", "sofa", "couch", "bench", "bed")
SEAT_DE = ("stuhl", "sessel", "sitz", "hocker", "bank", "bett", "liege")
SANITARY_EN = ("toilet", "urinal", "bidet", "lavatory", " wc", "shower", "bathtub", "bath", "sink", "basin", "kitchen", "cook", "stove")
SANITARY_DE = ("wc", "urinal", "dusche", "badewanne", "waschbecken", "waschtisch", "spuele", "spüle", "kueche", "küche", "herd")

NUMERIC_NAME_RE = re.compile(rb"^[\s\-_.]*\d+[\s\-_.]*$")


def _decode(raw):
    return raw.decode("latin-1", "replace").lower()


def _matches(text, keywords):
    return any(k in text for k in keywords)


def survey(path):
    row = {"file": path, "bytes": os.path.getsize(path)}
    with open(path, "rb") as fh:
        try:
            buf = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:
            return {**row, "error": "empty file"}
        try:
            head = buf[:65536]
            m = SCHEMA_RE.search(head)
            row["schema"] = m.group(1).decode() if m else None
            row["unit"], row["unit_scale"] = resolve_length_unit(buf)
            row["complete"] = buf[-4096:].rstrip().endswith(b"END-ISO-10303-21;")

            counts = collections.Counter(TOKEN_RE.findall(buf))
            row["n"] = {tok: counts.get(tok.encode(), 0) for tok in ENTITY_TOKENS}
            row["entities"] = sum(counts.values())

            props = collections.defaultdict(collections.Counter)
            for name, value in PROP_RE.findall(buf):
                v = value.strip().strip(b"'").upper()
                if name in (b"IsExternal", b"LoadBearing"):
                    key = "true" if v == b".T." else "false" if v == b".F." else "other"
                elif name == b"FireRating":
                    key = "unrated" if v in (b"", b"0", b"0.0", b"NONE", b"NO", b"N/A", b"-") else "rated"
                else:
                    key = "present"
                props[name.decode()][key] += 1
            row["props"] = {k: dict(v) for k, v in props.items()}

            virtual = sum(1 for rel in BOUNDARY_RE.findall(buf) if rel == b"$")
            row["boundaries"] = {"total": row["n"]["IFCRELSPACEBOUNDARY"], "virtual": virtual,
                                 "physical": row["n"]["IFCRELSPACEBOUNDARY"] - virtual}

            sp = {"named": 0, "numeric_only": 0, "unnamed": 0, "no_placement": 0, "no_representation": 0,
                  "circ_h_en": 0, "circ_h_de": 0, "circ_v_en": 0, "circ_v_de": 0, "distinct_names": 0}
            distinct = set()
            for name, placement, representation, longname in SPACE_RE.findall(buf):
                text_parts = [x.strip(b"'") for x in (name, longname) if x != b"$" and x.strip(b"'")]
                text = _decode(b" ".join(text_parts))
                if not text_parts:
                    sp["unnamed"] += 1
                elif all(NUMERIC_NAME_RE.match(x) for x in text_parts):
                    sp["numeric_only"] += 1
                else:
                    sp["named"] += 1
                    distinct.add(re.sub(r"\d+", "", text).strip())
                if placement == b"$":
                    sp["no_placement"] += 1
                if representation == b"$":
                    sp["no_representation"] += 1
                if _matches(text, CIRC_H_EN): sp["circ_h_en"] += 1
                if _matches(text, CIRC_H_DE): sp["circ_h_de"] += 1
                if _matches(text, CIRC_V_EN): sp["circ_v_en"] += 1
                if _matches(text, CIRC_V_DE): sp["circ_v_de"] += 1
            sp["distinct_names"] = len(distinct)
            row["spaces"] = sp
            row["space_name_samples"] = sorted(distinct)[:15]

            op = {"IFCWINDOW": collections.Counter(), "IFCDOOR": collections.Counter()}
            for cls, name, placement, representation, height, width in OPENING_RE.findall(buf):
                c = op[cls.decode()]
                c["total"] += 1
                if placement == b"$": c["no_placement"] += 1
                if representation == b"$": c["no_representation"] += 1
                if height == b"$" or width == b"$": c["no_overall_size"] += 1
            row["openings"] = {k: dict(v) for k, v in op.items()}
            flights = FLIGHT_RE.findall(buf)
            row["flights"] = {"total": len(flights), "no_placement": sum(1 for f in flights if f == b"$")}

            fx = collections.Counter()
            fixture_names = collections.Counter()
            for raw in FIXTURE_RE.findall(buf):
                text = _decode(raw.split(b":")[0])
                fixture_names[text] += 1
                fx["total"] += 1
                if _matches(text, SEAT_EN): fx["seat_en"] += 1
                if _matches(text, SEAT_DE): fx["seat_de"] += 1
                if _matches(text, SANITARY_EN): fx["sanitary_en"] += 1
                if _matches(text, SANITARY_DE): fx["sanitary_de"] += 1
            row["fixtures"] = dict(fx)
            row["fixture_name_samples"] = [n for n, _ in fixture_names.most_common(10)]
        finally:
            buf.close()
    return row


def iter_files(targets):
    for target in targets:
        if os.path.isdir(target):
            for root, _, files in os.walk(target):
                for name in sorted(files):
                    if name.lower().endswith(".ifc"):
                        yield os.path.join(root, name)
        else:
            yield target


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="+")
    parser.add_argument("--json", help="write all rows here")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    files = list(iter_files(args.targets))
    if args.limit:
        files = files[:args.limit]
    rows = []
    t0 = time.time()
    for i, path in enumerate(files, 1):
        try:
            rows.append(survey(path))
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the survey
            rows.append({"file": path, "error": f"{type(e).__name__}: {e}"})
        if i % 50 == 0 or i == len(files):
            print(f"  ... {i}/{len(files)} ({time.time() - t0:.0f}s)", file=sys.stderr, flush=True)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh)
        print(f"wrote {args.json} ({len(rows)} rows)")
    else:
        for r in rows:
            if "error" in r:
                print(r["file"], r["error"]); continue
            n, sp, pr = r["n"], r["spaces"], r["props"]
            print(f"{os.path.basename(r['file']):28} {r['schema']:8} {r['unit']:4} storeys={n['IFCBUILDINGSTOREY']:2} "
                  f"spaces={n['IFCSPACE']:4} named={sp['named']:4} numeric={sp['numeric_only']:3} circH en/de={sp['circ_h_en']}/{sp['circ_h_de']} "
                  f"circV en/de={sp['circ_v_en']}/{sp['circ_v_de']} doors={n['IFCDOOR']:3} win={n['IFCWINDOW']:3} "
                  f"bounds phys/virt={r['boundaries']['physical']}/{r['boundaries']['virtual']} "
                  f"IsExternal T/F={pr.get('IsExternal',{}).get('true',0)}/{pr.get('IsExternal',{}).get('false',0)} "
                  f"LoadBearing T={pr.get('LoadBearing',{}).get('true',0)} FireRating rated/unrated={pr.get('FireRating',{}).get('rated',0)}/{pr.get('FireRating',{}).get('unrated',0)} "
                  f"Span={pr.get('Span',{}).get('present',0)} mapped={n['IFCMAPPEDITEM']} fixtures={r['fixtures'].get('total',0)} seat en/de={r['fixtures'].get('seat_en',0)}/{r['fixtures'].get('seat_de',0)} "
                  f"san en/de={r['fixtures'].get('sanitary_en',0)}/{r['fixtures'].get('sanitary_de',0)}")


if __name__ == "__main__":
    main()
