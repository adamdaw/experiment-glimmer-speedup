#!/usr/bin/env python3
"""Minimal GGUF v3 metadata (KV) reader; stops before tensor infos. Usage: gguf_meta.py FILE [substr...]"""
import struct, sys
T = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
def rd(f, fmt): s = struct.calcsize("<" + fmt); return struct.unpack("<" + fmt, f.read(s))[0]
def rstr(f): n = rd(f, "Q"); return f.read(n).decode("utf-8", "replace")
def val(f, t):
    if t == 8: return rstr(f)
    if t == 9:
        et = rd(f, "I"); n = rd(f, "Q")
        if et in T and n > 64:
            f.seek(n * struct.calcsize(T[et]), 1); return f"<array {n} x type{et}>"
        return [val(f, et) for _ in range(n)] if n <= 64 else (f"<array {n} x type{et}>", [val(f, et) for _ in range(n)])[0]
    return rd(f, T[t])
fn, subs = sys.argv[1], sys.argv[2:]
with open(fn, "rb") as f:
    assert f.read(4) == b"GGUF"; ver = rd(f, "I"); nt = rd(f, "Q"); nkv = rd(f, "Q")
    print(f"{fn}: v{ver} tensors={nt} kv={nkv}")
    for _ in range(nkv):
        k = rstr(f); t = rd(f, "I"); v = val(f, t)
        if not subs or any(s in k for s in subs):
            print(f"  {k} = {v if not isinstance(v, str) or len(v) < 200 else v[:200] + '...'}")
