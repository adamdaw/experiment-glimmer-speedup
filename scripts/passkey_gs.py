#!/usr/bin/env python3
"""Exact passkey retrieval gate. Usage: passkey_gs.py MODEL --depths 2048,4096,... [--out F] [--reuse]
Real stdlib source as haystack; key at start/middle/end (3 placements x 1 seed each => 3 per depth, distinct keys).
Production sampling and reasoning (template default high). --reuse repeats each 8k/32k case on the warm slot."""
import argparse, json, random, re, sys, time
from gslib import *

ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("--depths", default="2048,4096,6144,8192,16384,32768,65536")
ap.add_argument("--out", required=True); ap.add_argument("--reuse", action="store_true"); ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
rng = random.Random(a.seed)
corpus = corpus_text()
Q = "\n\n---\nSomewhere in the text above there is a line of the form 'The secret passkey is N.' What is N? Reply with only the number."
ratio = None
for depth in [int(x) for x in a.depths.split(",")]:
    for place in ("start", "middle", "end"):
        key = str(rng.randint(10000, 99999)); needle = f"\n# The secret passkey is {key}. Remember it.\n"
        target = depth - 120
        if ratio is None:
            ratio = len(corpus[:40000]) / ntok(a.model, corpus[:40000])
        off = rng.randint(0, 50000)
        hay = corpus[off:off + int(target * ratio)]
        if len(hay) < target * ratio: hay = (corpus * 2)[off:off + int(target * ratio)]
        pos = {"start": 0.03, "middle": 0.5, "end": 0.97}[place]
        i = hay.find("\n", int(len(hay) * pos)); i = i if i > 0 else int(len(hay) * pos)
        text = hay[:i] + needle + hay[i:]
        msgs = [{"role": "user", "content": text + Q}]
        reps = 2 if (a.reuse and depth in (8192, 32768)) else 1
        for r in range(reps):
            res = chat_stream(a.model, msgs, 6000)
            ans = (res.get("content") or "").strip()
            nums = re.findall(r"\d{5}", ans)
            ok = (not res.get("error")) and nums == [key] and res.get("finish") == "stop" and repetition_score(res.get("reasoning", "") + ans) < 0.5
            t = res.get("timings") or {}
            rec = {"model": a.model, "depth": depth, "place": place, "rep": r, "key": key, "ok": ok, "answer": ans[:200],
                   "finish": res.get("finish"), "error": res.get("error"), "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"),
                   "pp": t.get("prompt_per_second"), "tg": t.get("predicted_per_second"), "gen_n": t.get("predicted_n"),
                   "reasoning_chars": len(res.get("reasoning") or ""), "rep_score": repetition_score(res.get("reasoning", "") + ans),
                   "total_s": round(res.get("total", 0), 1), "draft_n": t.get("draft_n"), "draft_acc": t.get("draft_n_accepted"),
                   "prod_running": running(), **meminfo()}
            open(a.out, "a").write(json.dumps(rec) + "\n")
            print(f"{a.model} depth={depth} {place} rep{r}: {'PASS' if ok else 'FAIL'} key={key} ans={ans[:60]!r} prompt_n={rec['prompt_n']} "
                  f"cache_n={rec['cache_n']} pp={rec['pp']} tg={rec['tg']} {rec['total_s']}s err={rec['error']}", flush=True)
