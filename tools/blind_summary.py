#!/usr/bin/env python3
"""De-anonymise blind grades with the key and summarise them per configuration.

Usage: tools/blind_summary.py GRADES.json KEY.json [--out grades_by_config.json]

GRADES.json: label -> task -> {correctness, groundedness, usefulness, completeness, concision, planted_bugs_found,
false_alarms, wrong_citations, hallucinated_citations, ...}. KEY.json: {"key": task -> label -> "<config> runN"}.

"cgu_mean" is the per-answer mean of correctness, groundedness and usefulness, averaged over answers. It is the
composite that reproduces the 3.82 / 3.79 / 3.74 quoted when the study was closed; the source did not document
which axes it used, so the five-axis mean is reported next to it.
"""
import argparse
import json
from collections import defaultdict

AXES = ["correctness", "groundedness", "usefulness", "completeness", "concision"]
CGU = ["correctness", "groundedness", "usefulness"]


def config_of(source):
    """'g-df7 run1' -> 'g-df7'; 'baseline-Q8 (2026-09-28 eval)' -> unchanged."""
    return source.rsplit(" run", 1)[0] if " run" in source else source


def summarise(grades, key):
    per = defaultdict(list)
    for label, tasks in grades.items():
        for task, g in tasks.items():
            per[config_of(key[task][label])].append(g)
    out = {}
    for cfg, gs in sorted(per.items()):
        n = len(gs)
        out[cfg] = {
            "n_answers": n,
            "cgu_mean": round(sum(sum(g[a] for a in CGU) / len(CGU) for g in gs) / n, 2),
            "five_axis_mean": round(sum(sum(g[a] for a in AXES) / len(AXES) for g in gs) / n, 2),
            **{f"{a}_mean": round(sum(g[a] for g in gs) / n, 2) for a in AXES},
            "planted_bugs_found": sum(g.get("planted_bugs_found") or 0 for g in gs),
            "planted_bugs_total": sum(g.get("planted_bugs_total") or 0 for g in gs),
            "false_alarms": sum(g.get("false_alarms") or 0 for g in gs),
            "wrong_citations": sum(g.get("wrong_citations") or 0 for g in gs),
            "hallucinated_citations": sum(g.get("hallucinated_citations") or 0 for g in gs),
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("grades"); ap.add_argument("key"); ap.add_argument("--out")
    a = ap.parse_args()
    res = summarise(json.load(open(a.grades)), json.load(open(a.key))["key"])
    txt = json.dumps(res, indent=2) + "\n"
    if a.out:
        open(a.out, "w").write(txt)
    print(txt, end="")


if __name__ == "__main__":
    main()
