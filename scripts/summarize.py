#!/usr/bin/env python3
"""Summarize bench_gs / passkey_gs / toolsmoke_gs outputs. Usage: summarize.py bench F [F...] | passkey F... | tools F..."""
import json, statistics as st, sys
from collections import defaultdict


def med(xs):
    xs = [x for x in xs if x is not None]
    return (st.median(xs), min(xs), max(xs), len(xs)) if xs else (None, None, None, 0)


def f(m, nd=1):
    v, lo, hi, n = m
    return "-" if v is None else f"{v:.{nd}f} [{lo:.{nd}f}-{hi:.{nd}f}] n={n}"


mode, files = sys.argv[1], sys.argv[2:]
rows = [json.loads(l) for fn in files for l in open(fn) if l.strip()]
if mode == "bench":
    g = defaultdict(list)
    for r in rows:
        if r["workload"] != "warmup": g[(r["model"], r["workload"])].append(r)
    order = ["review512", "reason512", "review8k", "review16k", "warm16k", "review32k", "review64k", "legacy256"]
    print("| model | workload | tg tok/s median [min-max] | pp tok/s median | TTFT s median | draft acc/drafted (rate) | errors | max swap GiB |")
    print("|---|---|---|---|---|---|---|---|")
    for (m, w) in sorted(g, key=lambda k: (k[0], order.index(k[1]) if k[1] in order else 99)):
        rs = g[(m, w)]
        dn = sum(r.get("draft_n") or 0 for r in rs); da = sum(r.get("draft_acc") or 0 for r in rs)
        acc = f"{da}/{dn} ({da / dn:.0%})" if dn else "-"
        errs = sum(1 for r in rs if r.get("error"))
        sw = max((r["mem_after"]["swap_used_gib"] for r in rs), default=None)
        print(f"| {m} | {w} | {f(med([r.get('tg') for r in rs]), 2)} | {f(med([r.get('pp') for r in rs]))} | "
              f"{f(med([r.get('ttft') for r in rs]), 2)} | {acc} | {errs} | {sw} |")
    bad = [r for r in rows if r.get("prod_running") and r["prod_running"] != []]
    print(f"\nrecords with a production model loaded concurrently: {len(bad)}")
elif mode == "passkey":
    g = defaultdict(list)
    for r in rows: g[(r["model"], r["depth"])].append(r)
    print("| model | depth | pass | prompt_n | pp tok/s | failures |"); print("|---|---|---|---|---|---|")
    for (m, d) in sorted(g):
        rs = g[(m, d)]; fails = [f"{r['place']}/r{r['rep']}: {r['answer'][:30]!r} {r['finish']} {r['error'] or ''}" for r in rs if not r["ok"]]
        print(f"| {m} | {d} | {sum(r['ok'] for r in rs)}/{len(rs)} | {rs[0]['prompt_n']} | {f(med([r['pp'] for r in rs if not r['cache_n']]))} | {'; '.join(fails) or '-'} |")
elif mode == "tools":
    g = defaultdict(list)
    for r in rows: g[r["model"]].append(r)
    for m, rs in g.items():
        tcf = [r for r in rs if r.get("calls") and r.get("reasoning_chars") == 0]
        print(f"{m}: {sum(r['ok'] for r in rs)}/{len(rs)} pass; cases={sorted(set(r['case'] for r in rs if not r['case'].startswith('first')))}; "
              f"true tool-call-first (no reasoning) records: {len(tcf)} ok={sum(r['ok'] for r in tcf)}; "
              f"fails={[(r['case'], r['stream'], r['problems']) for r in rs if not r['ok']]}")
