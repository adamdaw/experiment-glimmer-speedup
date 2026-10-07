#!/usr/bin/env python3
"""Tool-call smoke suite on /v1/chat/completions (same cases as an earlier model install test, 2026-09-27).

Cases, each run non-streaming and streaming (6 x 2 = 12):
  single         one call: get_weather(Oslo)
  parallel       three calls in ONE response: Paris, Tokyo, Lima (parallel_tool_calls=true)
  loop_t0/loop_t1 multi-turn: Oslo vs Madrid, results fed back (reasoning_content sent back), final answer must say Madrid
  hist_json      history with JSON-string args (nested object, unicode, quotes) -> new call get_weather(Rome)
  hist_plain     history with a finished tool exchange -> new call get_weather(Nairobi)
Usage: toolsmoke.py MODEL [--out results/toolsmoke.jsonl]
"""
import json, sys, time, urllib.request

import os
BASE = os.environ.get("GS_BASE", "http://localhost:8080")
MODEL = sys.argv[1]
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "results/toolsmoke.jsonl"
EXTRA = json.loads(sys.argv[sys.argv.index("--extra") + 1]) if "--extra" in sys.argv else {}

TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather", "description": "Get current weather for a city.",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string"}, "unit": {"type": "string", "enum": ["c", "f"]}}, "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "search_files", "description": "Search files for a regex; returns matching lines.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}, "path": {"type": "string"},
            "options": {"type": "object", "properties": {"ignore_case": {"type": "boolean"}, "max": {"type": "integer"}}}},
            "required": ["pattern"]}}},
]
MARKUP = ("<tool_call>", "<function=", "<think>", "</think>", "<|channel|>", "<|call|>", "<|start|>", "[TOOL_CALLS]", "[THINK]", "[ARGS]")


def post(body, stream):
    req = urllib.request.Request(BASE + "/v1/chat/completions", json.dumps(body).encode(), {"content-type": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=1800)
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:500]}, time.time() - t0
    if not stream:
        d = json.load(r)
        c = d["choices"][0]
        return {"message": c["message"], "finish": c.get("finish_reason"), "usage": d.get("usage"), "timings": d.get("timings")}, time.time() - t0
    msg = {"content": "", "reasoning_content": "", "tool_calls": {}}
    finish = None; timings = None
    for line in r:
        line = line.decode().strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        ch = json.loads(line[5:])
        timings = ch.get("timings", timings)
        if not ch.get("choices"):
            continue
        c = ch["choices"][0]; dlt = c.get("delta", {})
        msg["content"] += dlt.get("content") or ""
        msg["reasoning_content"] += dlt.get("reasoning_content") or ""
        for tc in dlt.get("tool_calls") or []:
            slot = msg["tool_calls"].setdefault(tc["index"], {"id": None, "type": "function", "function": {"name": "", "arguments": ""}})
            if tc.get("id"): slot["id"] = tc["id"]
            f = tc.get("function", {})
            slot["function"]["name"] += f.get("name") or ""
            slot["function"]["arguments"] += f.get("arguments") or ""
        finish = c.get("finish_reason") or finish
    msg["tool_calls"] = [msg["tool_calls"][k] for k in sorted(msg["tool_calls"])]
    return {"message": msg, "finish": finish, "timings": timings}, time.time() - t0


def call(messages, stream, **kw):
    return post({"model": MODEL, "messages": messages, "tools": TOOLS, "max_tokens": 8000, "stream": stream, **EXTRA, **kw}, stream)


def analyze(res):
    """-> (calls [(name, args|None)], problems [str])"""
    if "http_error" in res:
        return [], [f"HTTP {res['http_error']}: {res['body'][:200]}"]
    m = res["message"]; probs = []
    calls = []
    for tc in m.get("tool_calls") or []:
        raw = tc["function"]["arguments"]
        try:
            a = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(a, dict): raise ValueError("not an object")
            calls.append((tc["function"]["name"], a))
        except Exception as e:
            calls.append((tc["function"]["name"], None)); probs.append(f"unparseable args {raw[:120]!r} ({e})")
    content = m.get("content") or ""
    leaks = [t for t in MARKUP if t in content]
    if leaks: probs.append(f"markup leaked into content: {leaks}")
    if res.get("finish") == "length": probs.append("finish=length")
    return calls, probs


def city_set(calls):
    return sorted((a or {}).get("city", "?").split(",")[0].strip().lower() for n, a in calls if n == "get_weather")


def record(case, stream, res, dt, ok, probs, calls, extra=None):
    m = res.get("message") or {}
    rec = {"model": MODEL, "case": case, "stream": stream, "ok": ok, "problems": probs, "latency_s": round(dt, 1),
           "finish": res.get("finish"), "calls": calls, "content": (m.get("content") or "")[:400],
           "reasoning_chars": len(m.get("reasoning_content") or ""), **(extra or {})}
    with open(OUT, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(f"[{'stream' if stream else 'nonstream'} {case}] {'PASS' if ok else 'FAIL'} {dt:.1f}s finish={res.get('finish')} "
          f"calls={calls} content={(m.get('content') or '')[:100]!r} reasoning={len(m.get('reasoning_content') or '')} {probs}", flush=True)


for stream in (False, True):
    # 1 single
    res, dt = call([{"role": "user", "content": "What's the weather in Oslo right now? Use the tool."}], stream)
    calls, probs = analyze(res)
    if city_set(calls) != ["oslo"]: probs.append(f"expected one get_weather(Oslo), got {calls}")
    record("single", stream, res, dt, not probs, probs, calls)

    # 2 parallel
    res, dt = call([{"role": "user", "content": "Get the weather for Paris, Tokyo and Lima (celsius). Call the tool for all three cities at once in parallel."}],
                   stream, parallel_tool_calls=True)
    calls, probs = analyze(res)
    if city_set(calls) != ["lima", "paris", "tokyo"]: probs.append(f"expected 3 parallel get_weather calls, got {calls}")
    record("parallel", stream, res, dt, not probs, probs, calls)

    # 3 multi-turn loop
    msgs = [{"role": "user", "content": "Which is warmer right now, Oslo or Madrid? Look them up, then answer in one sentence."}]
    looked = set(); final = None; loop_probs = []
    for turn in range(5):
        res, dt = call(msgs, stream, parallel_tool_calls=True)
        calls, probs = analyze(res)
        m = res.get("message") or {}
        tcs = m.get("tool_calls") or []
        if not tcs:
            final = m.get("content") or ""
            if "madrid" not in final.lower(): probs.append(f"final answer does not name Madrid: {final[:150]!r}")
            if not {"oslo", "madrid"} <= looked: probs.append(f"answered without looking up both cities (looked up {sorted(looked)})")
            record(f"loop_t{turn}", stream, res, dt, not probs, probs, calls, {"final": True})
            loop_probs += probs
            break
        record(f"loop_t{turn}", stream, res, dt, not probs, probs, calls)
        loop_probs += probs
        msgs.append({"role": "assistant", "content": m.get("content") or "", "reasoning_content": m.get("reasoning_content") or "",
                     "tool_calls": [{"id": tc.get("id") or f"call_{turn}_{i}", "type": "function", "function": tc["function"]} for i, tc in enumerate(tcs)]})
        for i, tc in enumerate(tcs):
            try:
                city = json.loads(tc["function"]["arguments"]).get("city", "?")
            except Exception:
                city = "?"
            looked.add(city.split(",")[0].strip().lower())
            temp = {"oslo": 4, "madrid": 23}.get(city.split(",")[0].strip().lower(), 15)
            msgs.append({"role": "tool", "tool_call_id": tc.get("id") or f"call_{turn}_{i}", "content": json.dumps({"city": city, "temp_c": temp, "sky": "clear"})})
    else:
        record("loop_final", stream, res, dt, False, ["no final answer within 5 turns"], [])

    # 4 JSON-string args in history
    hist_args = json.dumps({"pattern": "def \"main\"\\(", "path": "src/ü", "options": {"ignore_case": True, "max": 5}})
    msgs = [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": "Find the main function in src/ü, then tell me which file it is in."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_a", "type": "function", "function": {"name": "search_files", "arguments": hist_args}}]},
        {"role": "tool", "tool_call_id": "call_a", "content": "src/ü/app.py:12:def \"main\"():"},
        {"role": "user", "content": "Good. Now also check the weather in Rome with the tool."},
    ]
    res, dt = call(msgs, stream)
    calls, probs = analyze(res)
    if city_set(calls) != ["rome"]: probs.append(f"expected get_weather(Rome), got {calls}")
    record("hist_json", stream, res, dt, not probs, probs, calls)

    # 5 plain history
    msgs = [
        {"role": "user", "content": "Weather in Bergen?"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_b", "type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"Bergen\"}"}}]},
        {"role": "tool", "tool_call_id": "call_b", "content": "{\"temp_c\": 7}"},
        {"role": "assistant", "content": "It is 7°C in Bergen."},
        {"role": "user", "content": "And in Nairobi?"},
    ]
    res, dt = call(msgs, stream)
    calls, probs = analyze(res)
    if city_set(calls) != ["nairobi"]: probs.append(f"expected get_weather(Nairobi), got {calls}")
    record("hist_plain", stream, res, dt, not probs, probs, calls)

# ---- added for the Glimmer speed programme: immediate tool-call-first (PR #29242 regression) ----
# Output that starts with " to=get_weather<|message|>..." with no analysis channel first. Low reasoning strength +
# an explicit instruction makes a no-reasoning first call likely; tool_choice=required exercises the non-lazy path.
FIRST_TRIES = int(os.environ.get("GS_FIRST_TRIES", "3"))
first_msgs = [{"role": "system", "content": "Respond ONLY by calling a tool. Never think, never write text before the call."},
              {"role": "user", "content": "get_weather Oslo. Call it immediately."}]
for stream in (False, True):
    for variant, kw in (("first_low", {"chat_template_kwargs": {"reasoning_strength": "low"}}),
                        ("first_high", {}),
                        ("first_required", {"tool_choice": "required", "chat_template_kwargs": {"reasoning_strength": "low"}})):
        for i in range(FIRST_TRIES):
            res, dt = call(first_msgs, stream, **kw)
            calls, probs = analyze(res)
            if city_set(calls) != ["oslo"]: probs.append(f"expected one get_weather(Oslo), got {calls}")
            m = res.get("message") or {}
            record(f"{variant}_{i}", stream, res, dt, not probs, probs, calls,
                   {"tool_call_first": not (m.get("reasoning_content") or "").strip()})
