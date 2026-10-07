#!/usr/bin/env python3
"""Assemble report tables from glimmer-speed results. Prints markdown."""
import json, glob, statistics as st, os
from pathlib import Path
from collections import defaultdict
R = os.environ.get("GS_RESULTS_DIR", str(Path(__file__).resolve().parent.parent / "runs"))
BASELINE = [os.environ.get("GS_BASELINE_STD", f"{R}/baseline_std.jsonl"), os.environ.get("GS_BASELINE_HARD", f"{R}/baseline_hard.jsonl")]
def jl(p): return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
def med(xs):
    xs = [x for x in xs if x is not None]; return st.median(xs) if xs else None
def rng(xs):
    xs = [x for x in xs if x is not None]; return f"{min(xs):.1f}–{max(xs):.1f}" if xs else "-"

# speed matrix
M = jl(f"{R}/matrix.jsonl")
W = ["review512", "reason512", "review8k", "review16k", "review32k", "review64k", "warm16k", "legacy256"]
g = defaultdict(list)
for r in M:
    if r["workload"] != "warmup": g[(r["model"], r["workload"])].append(r)
models = sorted({m for m, _ in g}, key=lambda m: ["g-a1", "g-df7", "g-q5", "g-combo1"].index(m) if m in ["g-a1", "g-df7", "g-q5", "g-combo1"] else 9)
print("### Decode tok/s (median, min–max, n)\n")
print("| config | " + " | ".join(W) + " |"); print("|---" * (len(W) + 1) + "|")
for m in models:
    cells = []
    for w in W:
        rs = g.get((m, w), [])
        v = med([r["tg"] for r in rs]); cells.append(f"{v:.2f} ({rng([r['tg'] for r in rs])}, n={len(rs)})" if v else "-")
    print(f"| {m} | " + " | ".join(cells) + " |")
print("\n### Prefill tok/s (cold prompt cache) and TTFT s (median)\n")
PW = ["review512", "review8k", "review16k", "review32k", "review64k", "warm16k"]
print("| config | " + " | ".join(f"{w} pp / TTFT" for w in PW) + " |"); print("|---" * (len(PW) + 1) + "|")
for m in models:
    cells = []
    for w in PW:
        rs = g.get((m, w), [])
        pp = med([r["pp"] for r in rs]); tt = med([r["ttft"] for r in rs])
        cells.append(f"{pp:.0f} / {tt:.1f}" if pp and tt is not None else "-")
    print(f"| {m} | " + " | ".join(cells) + " |")
print("\n### Draft acceptance (accepted / drafted, all reps)\n")
print("| config | " + " | ".join(W[:7]) + " |"); print("|---" * 8 + "|")
for m in models:
    cells = []
    for w in W[:7]:
        rs = g.get((m, w), []); dn = sum(r.get("draft_n") or 0 for r in rs); da = sum(r.get("draft_acc") or 0 for r in rs)
        cells.append(f"{da / dn:.0%} ({da}/{dn})" if dn else "-")
    print(f"| {m} | " + " | ".join(cells) + " |")
errs = [r for r in M if r.get("error")]; conc = [r for r in M if r.get("prod_running")]
print(f"\nmatrix records: {len(M)}; errors: {len(errs)}; records with a production model loaded: {len(conc)}; "
      f"finish=length on 512 tasks: {sum(1 for r in M if r['workload'] in ('review512','reason512') and r.get('finish')=='length')}; "
      f"max rep_score: {max((r.get('rep_score') or 0) for r in M) if M else '-'}; "
      f"min MemAvailable GiB: {min((r['mem_after']['mem_avail_gib'] for r in M), default='-')}; max swap GiB: {max((r['mem_after']['swap_used_gib'] for r in M), default='-')}")

# quality objective
print("\n### Review/explore objective checks (harness auto-scorer; blind grading pending)\n")
print("| config | run | std recall | std auto-FP | hard recall | hard auto-FP | answers | finish!=stop | median wall s review / explore |")
print("|---|---|---|---|---|---|---|---|---|")
base = [r for f in BASELINE for r in jl(f)
        if r["model"] == "muse-glimmer-30b" and r.get("kind") in ("review", "explore")]
def qrow(name, run, rs):
    std = [r for r in rs if r.get("kind") == "review" and r["task"].startswith("r")]; hard = [r for r in rs if r.get("kind") == "review" and r["task"].startswith("hr")]
    def rec(x): return f"{sum(round(r['review_score']['recall'] * len(r['review_score']['found'])) for r in x)}/{sum(len(r['review_score']['found']) for r in x)}" if x else "-"
    def fp(x): return str(sum(r["review_score"]["false_positives"] for r in x)) if x else "-"
    wr = med([r.get("wall_s") for r in rs if r["kind"] == "review"]); we = med([r.get("wall_s") for r in rs if r["kind"] == "explore"])
    print(f"| {name} | {run} | {rec(std)} | {fp(std)} | {rec(hard)} | {fp(hard)} | {len(rs)} | {sum(1 for r in rs if r.get('finish_reason') != 'stop')} | "
          f"{wr and round(wr)} / {we and round(we)} |")
qrow("baseline Q8 (2026-09-28)", 1, base)
for c in ["g-df7", "g-q5", "g-combo1"]:
    for run in (1, 2):
        rs = jl(f"{R}/q_{c}_std_r{run}.jsonl") + jl(f"{R}/q_{c}_hard_r{run}.jsonl")
        if rs: qrow(c, run, rs)
