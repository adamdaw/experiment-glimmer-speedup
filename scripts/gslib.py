"""Shared helpers for the Glimmer speed programme (temporary llama-swap at GS_BASE)."""
import glob, json, os, random, sysconfig, time, urllib.request

BASE = os.environ.get("GS_BASE", "http://localhost:8080")
# Optional second llama-swap whose /running list is logged with every record (concurrency check). Empty = skip.
PROD = os.environ.get("GS_PROD_BASE", "")
# Haystack source. The study used the system Python 3.1x stdlib of a Fedora host ("/usr/lib64/python3.1*").
STDLIB_GLOB = os.environ.get("GS_STDLIB_GLOB", sysconfig.get_paths()["stdlib"])
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0.0}  # = production server defaults


def req(path, body=None, method=None, base=None, timeout=7200):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request((base or BASE) + path, data, {"content-type": "application/json"}, method=method)
    return urllib.request.urlopen(r, timeout=timeout)


def corpus_text():
    """Deterministic real-source corpus (~700k chars) from the Python stdlib."""
    pats = ["json/*.py", "email/*.py", "asyncio/*.py", "http/*.py", "logging/*.py", "concurrent/futures/*.py",
            "unittest/*.py", "importlib/*.py", "xml/etree/*.py", "urllib/*.py", "collections/*.py"]
    files = []
    for p in pats:
        files += sorted(glob.glob(f"{STDLIB_GLOB}/{p}"))[:60]
    seen = set(); out = []
    for f in files:
        b = os.path.basename(os.path.dirname(f)) + "/" + os.path.basename(f)
        if b in seen: continue
        seen.add(b); out.append(f"\n### FILE {b}\n" + open(f, errors="replace").read())
    return "".join(out)


def ntok(model, text):
    return len(json.load(req(f"/upstream/{model}/tokenize", {"content": text}))["tokens"])


def running():
    if not PROD:
        return []
    try:
        return [m["model"] for m in json.load(req("/running", base=PROD, timeout=10))["running"]]
    except Exception as e:
        return [f"ERR {e}"]


def chat_stream(model, messages, max_tokens, extra=None):
    """-> dict(ttft, total, timings, content, reasoning, finish, error)"""
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True,
            "timings_per_token": False, **SAMPLING, **(extra or {})}
    t0 = time.time(); ttft = None; timings = None; content = ""; reasoning = ""; finish = None
    try:
        for line in req("/v1/chat/completions", body):
            line = line.decode().strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            ch = json.loads(line[5:])
            timings = ch.get("timings", timings)
            if not ch.get("choices"):
                continue
            c = ch["choices"][0]; d = c.get("delta", {})
            piece = (d.get("content") or "") + (d.get("reasoning_content") or "")
            if ttft is None and (piece or d.get("tool_calls")):
                ttft = time.time() - t0
            content += d.get("content") or ""; reasoning += d.get("reasoning_content") or ""
            finish = c.get("finish_reason") or finish
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:300]}", "total": time.time() - t0}
    except Exception as e:
        return {"error": repr(e)[:300], "total": time.time() - t0}
    return {"ttft": ttft, "total": time.time() - t0, "timings": timings, "content": content,
            "reasoning": reasoning, "finish": finish}


def meminfo():
    m = {}
    for l in open("/proc/meminfo"):
        k, v = l.split(":"); m[k] = int(v.split()[0])
    gtt = None
    for p in glob.glob("/sys/class/drm/card*/device/mem_info_gtt_used"):
        try: gtt = int(open(p).read()) / 2**30
        except Exception: pass
    return {"mem_avail_gib": round(m["MemAvailable"] / 2**20, 1), "swap_used_gib": round((m["SwapTotal"] - m["SwapFree"]) / 2**20, 2),
            "gtt_used_gib": round(gtt, 1) if gtt is not None else None}


def repetition_score(text, n=40):
    """fraction of repeated 40-char windows in the tail: >0.5 suggests a repetition collapse."""
    t = text[-4000:]
    if len(t) < 400: return 0.0
    grams = [t[i:i + n] for i in range(0, len(t) - n, 20)]
    return round(1 - len(set(grams)) / len(grams), 3)
