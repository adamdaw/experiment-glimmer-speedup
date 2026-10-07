#!/usr/bin/env python3
"""Greedy (temp 0, top_k 1) output comparison: speculative/other config vs control, same prompts.
Diagnostic only: target verification should make speculative output match the control token-for-token,
except for rare numeric divergence from different batch shapes. Usage: greedy_gs.py CONTROL CAND [CAND...] --out F"""
import json, sys
from gslib import chat_stream
out = sys.argv[sys.argv.index("--out") + 1]; models = [m for m in sys.argv[1:sys.argv.index("--out")]]
P = ["Explain, step by step, why binary search on a sorted array runs in O(log n) time, then write a Python implementation with tests.",
     "def merge(a, b):\n    out = []\n    i = j = 0\n    while i < len(a) and j < len(b):\n        if a[i] < b[j]:\n            out.append(a[i]); i += 1\n        else:\n            out.append(b[j]); j += 1\n    return out\n\nReview this function. Quote any buggy line verbatim and give a fixed version.",
     "A train leaves at 09:40 and arrives at 13:05 the same day, with a 25-minute stop. What is the moving time? Show the arithmetic."]
for m in models:
    for i, p in enumerate(P):
        r = chat_stream(m, [{"role": "user", "content": p}], 700, {"temperature": 0.0, "top_k": 1, "seed": 1, "chat_template_kwargs": {"reasoning_strength": "low"}})
        t = r.get("timings") or {}
        open(out, "a").write(json.dumps({"model": m, "prompt": i, "content": r.get("content"), "reasoning": r.get("reasoning"),
                                         "error": r.get("error"), "tg": t.get("predicted_per_second"), "draft_n": t.get("draft_n"),
                                         "draft_acc": t.get("draft_n_accepted")}) + "\n")
        print(m, i, t.get("predicted_per_second"), r.get("error"), flush=True)
rows = [json.loads(l) for l in open(out)]
ctl = {r["prompt"]: r for r in rows if r["model"] == models[0]}
for r in rows:
    if r["model"] == models[0]: continue
    a = (ctl[r["prompt"]]["reasoning"] or "") + (ctl[r["prompt"]]["content"] or ""); b = (r["reasoning"] or "") + (r["content"] or "")
    n = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    print(f"{r['model']} p{r['prompt']}: identical={a == b} common_prefix_chars={n}/{max(len(a), len(b))}")
