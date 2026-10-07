#!/usr/bin/env python3
"""Speed matrix for Glimmer candidates. Blocks alternate model order each repetition (A B, B A, ...).
Each block: tiny warm-up (absorbs model load), then the workloads. Every prompt has a fresh nonce prefix
(cold prompt cache) except warm16k, which reuses the preceding 16k prefix. Production sampling; reasoning at the
template default (HIGH) unless stated. Usage: bench_gs.py --models g-a1,g-b --reps 5 --ctx 8192,16384,32768 --out F"""
import argparse, json, random, time
from gslib import *

ap = argparse.ArgumentParser()
ap.add_argument("--models", required=True); ap.add_argument("--reps", type=int, default=5)
ap.add_argument("--ctx", default="8192,16384,32768"); ap.add_argument("--short-gen", type=int, default=1024)
ap.add_argument("--long-gen", type=int, default=384); ap.add_argument("--legacy", action="store_true")
ap.add_argument("--no-short", action="store_true"); ap.add_argument("--out", required=True)
a = ap.parse_args()
models = a.models.split(","); ctxs = [int(c) for c in a.ctx.split(",") if c]
corpus = corpus_text()
REASON = [
    "A bakery sells muffins in boxes of 4 and 9. What is the largest number of muffins that cannot be bought exactly? Explain the reasoning carefully and check it.",
    "Three engineers disagree about whether to add a cache in front of a slow billing API. List the strongest argument for each of three positions (add it, don't, add it with constraints), then decide and justify.",
    "Is it possible to tile an 8x8 board with two opposite corners removed using 1x2 dominoes? Reason it through and then state the general principle.",
    "A team's p99 latency doubled after a deploy that only changed logging. Give a ranked list of plausible causes with how you would test each, then pick the most likely one and explain.",
    "Explain why the sum 1 + 1/2 + 1/3 + ... diverges while 1 + 1/4 + 1/9 + ... converges, with a rigorous argument for each and an intuitive one.",
]
SNIP_OFFS = [100_000, 400_000, 700_000, 1_000_000, 1_300_000]


def review_prompt(text):
    return (text + "\n\n---\nReview the code above as a senior reviewer. Identify the most important correctness risks. "
            "For each, quote the exact line(s) verbatim in a code block, then explain the problem and the fix.")


def one(model, label, msgs, gen, rep, extra=None):
    mem0 = meminfo(); res = chat_stream(model, msgs, gen, extra); t = res.get("timings") or {}
    rec = {"model": model, "workload": label, "rep": rep, "error": res.get("error"), "ttft": res.get("ttft"),
           "total_s": res.get("total"), "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"),
           "pp": t.get("prompt_per_second"), "gen_n": t.get("predicted_n"), "tg": t.get("predicted_per_second"),
           "draft_n": t.get("draft_n"), "draft_acc": t.get("draft_n_accepted"), "finish": res.get("finish"),
           "reasoning_chars": len(res.get("reasoning") or ""), "content_chars": len(res.get("content") or ""),
           "rep_score": repetition_score((res.get("reasoning") or "") + (res.get("content") or "")),
           "timings": t, "prod_running": running(), "mem_before": mem0, "mem_after": meminfo(), "ts": time.time()}
    open(a.out, "a").write(json.dumps(rec) + "\n")
    print(f"{model:8s} r{rep} {label:12s} ttft={rec['ttft'] and round(rec['ttft'],2)} prompt_n={rec['prompt_n']} "
          f"pp={rec['pp'] and round(rec['pp'],1)} gen_n={rec['gen_n']} tg={rec['tg'] and round(rec['tg'],2)} "
          f"draft={rec['draft_acc']}/{rec['draft_n']} err={rec['error']} swap={rec['mem_after']['swap_used_gib']} prod={rec['prod_running']}", flush=True)
    return rec


ratio = None
for rep in range(a.reps):
    order = models if rep % 2 == 0 else list(reversed(models))
    for model in order:
        one(model, "warmup", [{"role": "user", "content": f"[{random.random()}] Say OK."}], 16, rep,
            {"chat_template_kwargs": {"reasoning_strength": "low"}})
        if ratio is None:
            ratio = len(corpus[:40000]) / ntok(model, corpus[:40000])
        if not a.no_short:
            off = SNIP_OFFS[rep % 5]
            snip = corpus[off:off + int(430 * ratio)]
            one(model, "review512", [{"role": "user", "content": f"[{random.random()}]\n" + review_prompt(snip)}], a.short_gen, rep)
            one(model, "reason512", [{"role": "user", "content": f"[{random.random()}] " + REASON[rep % 5]}], a.short_gen, rep)
        for c in ctxs:
            off = (rep * 97_000) % 600_000
            text = corpus[off:off + int((c - 150) * ratio)]
            nonce = f"[{random.random()}]\n"
            one(model, f"review{c // 1024}k", [{"role": "user", "content": nonce + review_prompt(text)}], a.long_gen, rep)
            if c == 16384:  # warm prefix: same document, different question
                one(model, "warm16k", [{"role": "user", "content": nonce + text + "\n\n---\nList the public functions defined above, one per line."}],
                    a.long_gen, rep)
        if a.legacy:  # the 2026-09-27 bench_speed fixture: 256 tokens, ignore_eos, reasoning low
            one(model, "legacy256", [{"role": "user", "content": f"[{random.random()}] Write a detailed essay about the history of the printing press."}],
                256, rep, {"ignore_eos": True, "chat_template_kwargs": {"enable_thinking": False, "reasoning_strength": "low"}})
