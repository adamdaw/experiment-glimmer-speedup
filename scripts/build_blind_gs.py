#!/usr/bin/env python3
"""Blind grading packet for the Glimmer speed programme (same format as the parent eval's earlier packet).

Packet: runs/grading-packet/packet.md (no model/config names). Key: runs/KEY.json (grader must not read).
Per task: the baseline Q8 answer (GS_BASELINE_STD / GS_BASELINE_HARD harness output files, model muse-glimmer-30b)
plus two runs of every candidate listed in argv (files runs/q_<cand>_<std|hard>_r<1|2>.jsonl).
Labels shuffled independently per task. Refuses to overwrite an existing key unless --force.
Usage: build_blind_gs.py g-df7 g-q5 ... [--force]"""
import json, os, random, secrets, sys
from pathlib import Path

from blind_text import RUBRIC, SCRUB, EXPLORE_RUBRIC_EXTRA  # (RUBRIC text, as in the earlier packet)

ER = Path(os.environ.get("GS_EVAL_ROOT", Path(__file__).resolve().parent.parent))
RUNS = Path(os.environ.get("GS_RESULTS_DIR", ER / "runs"))
BASE_STD = Path(os.environ.get("GS_BASELINE_STD", RUNS / "baseline_std.jsonl"))
BASE_HARD = Path(os.environ.get("GS_BASELINE_HARD", RUNS / "baseline_hard.jsonl"))
PDIR = RUNS / "grading-packet"; KEYF = RUNS / "KEY.json"
LABELS = list("ABCDEFGHJKLMNPQRSTUVWXYZ")


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def main():
    cands = [a for a in sys.argv[1:] if not a.startswith("--")]
    if KEYF.exists() and "--force" not in sys.argv:
        sys.exit(f"{KEYF} exists; pass --force to reshuffle")
    pool = {"standard": [], "hard": []}
    for r in jl(BASE_STD):
        if r["model"] == "muse-glimmer-30b" and r.get("kind") in ("review", "explore"):
            pool["standard"].append({**r, "_src": "baseline-Q8 (2026-09-28 eval)"})
    for r in jl(BASE_HARD):
        if r["model"] == "muse-glimmer-30b" and r.get("kind") in ("review", "explore"):
            pool["hard"].append({**r, "_src": "baseline-Q8 (2026-09-28 eval)"})
    for c in cands:
        for tset, tag in (("standard", "std"), ("hard", "hard")):
            for run in (1, 2):
                f = RUNS / f"q_{c}_{tag}_r{run}.jsonl"
                if f.exists():
                    pool[tset] += [{**r, "_src": f"{c} run{run}"} for r in jl(f) if r.get("kind") in ("review", "explore")]
    items = []
    for tset, tdir in (("standard", "tasks"), ("hard", "tasks_hard")):
        rub = json.loads((ER / tdir / "review" / "rubric.json").read_text())
        for name in sorted(rub):
            ref = "Planted bugs (the diff was constructed with these):\n" + "\n".join(f"- {b['desc']}" for b in rub[name]["planted"])
            items.append(("review", name, ref, tset))
        for d in sorted((ER / tdir / "explore").iterdir()):
            if d.is_dir():
                items.append(("explore", d.name, (d / "reference.md").read_text(), tset))
    rng = random.Random(secrets.randbits(64))
    key, scrubbed, counts = {}, {}, {}
    md = ["# Blind grading packet (local-model eval, batch GS)\n",
          f"{len(items)} tasks: code reviews with planted bugs and explore/explain questions. Each task has the exact prompt, "
          "reference notes and several anonymous answers. Labels are shuffled independently per task, so A in one task is unrelated to A in another.\n",
          RUBRIC, EXPLORE_RUBRIC_EXTRA,
          "For review tasks, also count per answer: planted bugs found (0-2) and false alarms (claims that are wrong or not defects; "
          "real-but-unplanted issues are fine).\n"]
    for kind, name, ref, tset in items:
        recs = [r for r in pool[tset] if r.get("kind") == kind and r["task"] == name and "harness_error" not in r]
        rng.shuffle(recs)
        labels = LABELS[:len(recs)]
        key[name] = {lab: r["_src"] for lab, r in zip(labels, recs)}
        counts[name] = len(recs)
        prompt = recs[0]["prompt"] if recs else "(missing)"
        md.append(f"\n---\n\n# Task `{name}` ({kind}, {tset} set)\n")
        md.append("<details><summary>Full prompt given to the models (click to expand)</summary>\n\n````text\n" + prompt + "\n````\n</details>\n")
        md.append("### Reference notes\n\n" + ref.strip() + "\n")
        for lab, r in zip(labels, recs):
            ans = (r.get("answer") or "").strip() or f"(no answer: {r.get('error') or 'empty response'})"
            ans, n = SCRUB.subn("[model]", ans)
            if n: scrubbed[f"{name}|{lab}"] = n
            trunc = " (answer was cut off by the token limit)" if r.get("finish_reason") == "length" else ""
            md.append(f"\n### Answer {lab}{trunc}\n\n" + ans + "\n")
    PDIR.mkdir(exist_ok=True)
    txt = "\n".join(md) + "\n"
    leftover = SCRUB.findall(txt.split("# Task", 1)[1]) if "# Task" in txt else []
    (PDIR / "packet.md").write_text(txt)
    KEYF.write_text(json.dumps({"note": "label -> source per task; DO NOT show to the grader. Packet: runs/grading-packet/packet.md",
                                "candidates": cands, "key": key, "scrubbed_mentions": scrubbed}, indent=2) + "\n")
    KEYF.chmod(0o600)
    print(f"wrote {PDIR / 'packet.md'} ({len(txt)} chars), answers per task {counts}; key {KEYF}; scrubbed {sum(scrubbed.values())}; leftover={leftover[:10]}")


if __name__ == "__main__":
    main()
