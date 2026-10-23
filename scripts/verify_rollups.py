"""Self-checks for the 2026-10-09 rollups: one stack companion per storey
transition, a window cluster that equals a stack dropped, a member count noted on big records. Synthetic
only: hand-built chains and record lists, no IFC file, nothing written.

    uv run python scripts/verify_rollups.py

Exit code 0 when every check passes, 1 otherwise.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def section_companions():
    from recognition.detectors.structural import _discontinuity_intents
    # Four storeys S0..S3 carrying columns; stack A spans S0..S2, stack B spans S1..S2, stack C spans S0..S3.
    storey_rank = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}
    names = {0: "Level 0", 1: "Level 1", 2: "Level 2", 3: "Level 3"}
    chains = [
        (["a0", "a1", "a2"], [0, 1, 2], ["Level 0", "Level 1", "Level 2"]),
        (["b1", "b2"], [1, 2], ["Level 1", "Level 2"]),
        (["c0", "c1", "c2", "c3"], [0, 1, 2, 3], ["Level 0", "Level 1", "Level 2", "Level 3"]),
    ]
    records = _discontinuity_intents(None, chains, storey_rank, names, "k", "column", "IfcColumn")
    stops = [r for r in records if r["type"] == "structural_stack_termination"]
    bases = [r for r in records if r["type"] == "structural_unsupported_base"]
    check("two stacks ending at Level 2 give ONE termination record", len(stops) == 1, [r["id"] for r in stops])
    if stops:
        s = stops[0]
        check("its id is built from the storey, its members are the two top columns, role top",
              s["id"] == "k-columnstop-S2" and sorted(m["guid"] for m in s["members"]) == ["a2", "b2"]
              and all(m["role"] == "top" for m in s["members"]), (s["id"], s["members"]))
        check("its metrics count the stacks and name the positive records",
              s["evidence"]["metrics"]["stackCount"] == 2 and s["evidence"]["metrics"]["continuesWithoutMatchOn"] == ["Level 3"]
              and sorted(s["evidence"]["metrics"]["stackIds"]) == ["k-colsupport-a0-a1-a2", "k-colsupport-b1-b2"], s["evidence"]["metrics"])
        check("label and polarity", s["label"] == "2 column stacks end at Level 2 (1 storey above)" and s["polarity"] == "negative"
              and s["evidence"]["relatedGuids"] == ["S2"], s["label"])
    check("one stack without support below gives one base record with that stack's base column",
          len(bases) == 1 and bases[0]["id"] == "k-columnnobase-S1" and [m["guid"] for m in bases[0]["members"]] == ["b1"]
          and bases[0]["members"][0]["role"] == "base" and bases[0]["evidence"]["metrics"]["stopsAboveStoreys"] == ["Level 0"]
          and bases[0]["label"] == "1 column stack has no support below Level 1 (1 storey beneath)", [(r["id"], r["label"]) for r in bases])
    check("a full-height stack produces no companion", all("c" not in m["guid"] for r in records for m in r["members"]))
    def comparable(recs):
        return [{k: v for k, v in r.items() if k != "provenance"} for r in recs]
    check("determinism: input order does not change the records",
          comparable(_discontinuity_intents(None, list(reversed(chains)), storey_rank, names, "k", "column", "IfcColumn")) == comparable(records))
    check("base record: membersPerStack is each stack's length, the storey is the related element",
          bases and bases[0]["evidence"]["metrics"]["membersPerStack"] == [2] and bases[0]["evidence"]["relatedGuids"] == ["S1"])
    branching = _discontinuity_intents(None, [(["d0", "d1", "d1b"], [0, 1, 1], ["Level 0", "Level 1", "Level 1"])],
                                       storey_rank, names, "k", "column", "IfcColumn")
    check("a branching stack contributes every element at its terminal rank",
          [m["guid"] for r in branching for m in r["members"]] == ["d1", "d1b"] and branching[0]["evidence"]["metrics"]["membersPerStack"] == [3],
          [(r["id"], [m["guid"] for m in r["members"]]) for r in branching])
    walls = _discontinuity_intents(None, [(["w1", "w2"], [1, 2], ["Level 1", "Level 2"])], storey_rank, names, "k", "wall", "IfcWall")
    check("walls roll up under their own kind and rule",
          sorted(r["id"] for r in walls) == ["k-wallnobase-S1", "k-wallstop-S2"] and all(r["provenance"]["rule"].startswith("wall_") for r in walls)
          and walls[0]["members"][0]["ifcClass"] == "IfcWall", [r["id"] for r in walls])


def section_clusters():
    from recognition.detectors.window_patterns import drop_clusters_equal_to_stacks
    from recognition.intent import make_intent, make_member
    def rec(rid, rtype, guids):
        metrics = {"typeName": "W1", "verdictCounts": {"exterior": 3}} if rid == "cluster1" else {}
        return make_intent(rid, rtype, rid, [make_member(g, ifc_class="IfcWindow") for g in guids], "window_patterns", "s", metrics=metrics)
    records = [rec("stack1", "window_vertical_alignment", ["a", "b", "c"]),
               rec("cluster1", "window_lighting_cluster", ["a", "b", "c"]),
               rec("cluster2", "window_lighting_cluster", ["a", "b", "c", "d"]),
               rec("bay1", "window_bay_interrupted", ["a", "b"])]
    kept = drop_clusters_equal_to_stacks(records)
    check("a cluster equal to a stack is dropped, other records stay in order",
          [r["id"] for r in kept] == ["stack1", "cluster2", "bay1"], [r["id"] for r in kept])
    check("the stack notes it was also its own cluster", kept[0]["evidence"]["metrics"].get("alsoLightingCluster") is True)
    check("the dropped cluster's claims move onto the stack: window type and the per-window verdicts",
          kept[0]["evidence"]["metrics"].get("clusterTypeName") == "W1"
          and kept[0]["evidence"]["metrics"].get("clusterVerdictCounts") == {"exterior": 3}, kept[0]["evidence"]["metrics"])
    check("a cluster with no stack twin is untouched", "alsoLightingCluster" not in kept[1]["evidence"]["metrics"])


def section_member_count():
    from recognition.intent import make_intent, make_member
    big = make_intent("b", "t", "b", [make_member(str(i)) for i in range(201)], "d", "s")
    small = make_intent("s", "t", "s", [make_member("x"), make_member("y")], "d", "s")
    check("a record with more than 200 members carries memberCount", big["evidence"]["metrics"].get("memberCount") == 201 and len(big["members"]) == 201)
    check("a small record carries no memberCount", "memberCount" not in small["evidence"]["metrics"])


def main():
    for section in (section_companions, section_clusters, section_member_count):
        try:
            section()
        except Exception as e:  # noqa: BLE001 - a crashing section is a failed check, not a crash
            check(f"{section.__name__} runs", False, f"{type(e).__name__}: {e}")
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f"  ->  {detail}"))
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
