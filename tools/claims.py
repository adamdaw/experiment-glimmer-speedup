#!/usr/bin/env python3
"""Recompute every number quoted in README.md from the committed results/ files (no raw transcripts needed).

Usage: tools/claims.py [RESULTS_DIR]   (default: results/ next to this repo's tools/)
Prints markdown sections; tests/test_claims.py pins the values the README quotes.
"""
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ORDER = ["g-a1", "g-df7", "g-q5", "g-combo1"]
WORKLOADS = ["review512", "reason512", "review8k", "review16k", "review32k", "review64k", "warm16k", "legacy256"]


def rows(results, name):
    with open(Path(results) / name, newline="") as fh:
        return list(csv.DictReader(fh))


def num(x):
    return float(x) if x not in ("", None, "None") else None


def group(rs, *keys):
    g = defaultdict(list)
    for r in rs:
        g[tuple(r[k] for k in keys)].append(r)
    return g


def speed_matrix(results):
    """-> {(config, workload): {"tg_median", "tg_min", "tg_max", "pp_median", "ttft_median", "draft_n", "draft_acc", "n"}}"""
    out = {}
    for (cfg, wl), rs in group([r for r in rows(results, "speed_matrix.csv") if r["workload"] != "warmup"],
                               "config", "workload").items():
        tg = [num(r["tg_tok_s"]) for r in rs]
        out[(cfg, wl)] = {"n": len(rs), "tg_median": st.median(tg), "tg_min": min(tg), "tg_max": max(tg),
                          "pp_median": st.median(num(r["pp_tok_s"]) for r in rs),
                          "ttft_median": st.median(num(r["ttft_s"]) for r in rs),
                          "draft_n": sum(int(r["draft_n"] or 0) for r in rs),
                          "draft_acc": sum(int(r["draft_accepted"] or 0) for r in rs)}
    return out


def matrix_health(results):
    rs = rows(results, "speed_matrix.csv")
    return {"records": len(rs), "errors": sum(1 for r in rs if r["error"]),
            "concurrent": sum(1 for r in rs if int(r["concurrent_server_models"])),
            "finish_length_512": sum(1 for r in rs if r["workload"] in ("review512", "reason512") and r["finish"] == "length"),
            "max_rep_score": max(num(r["rep_score"]) or 0 for r in rs),
            "max_swap_gib": max(num(r["swap_used_gib_after"]) for r in rs)}


def screen(results):
    out = {}
    # each config from the run that screened it: g-combo1 from screen_combo, everything else from the main screen
    sel = [r for r in rows(results, "screen.csv") if r["workload"] != "warmup"
           and (r["source"] == "screen_combo") == (r["config"] == "g-combo1")]
    for (cfg, wl), rs in group(sel, "config", "workload").items():
        out[(cfg, wl)] = st.median(num(r["tg_tok_s"]) for r in rs)
    return out


def passkey(results):
    out = {}
    for (cfg,), rs in group(rows(results, "passkey.csv"), "config").items():
        out[cfg] = (sum(r["ok"] == "True" for r in rs), len(rs), max(int(r["prompt_n"]) for r in rs))
    return out


def tools(results):
    out = {}
    tpl = group(rows(results, "tplcheck.csv"), "config")
    for (cfg,), rs in group(rows(results, "toolsmoke.csv"), "config").items():
        hist = [r for r in rs if not r["case"].startswith("first")]
        first = [r for r in rs if r["case"].startswith("first")]
        out[cfg] = {"historical": (sum(r["ok"] == "True" for r in hist), len(hist)),
                    "first": (sum(r["ok"] == "True" for r in first), len(first)),
                    "first_without_reasoning": sum(r["tool_call_first"] == "True" for r in first),
                    "no_reasoning_call": sum(r["no_reasoning_call"] == "True" for r in rs),
                    "no_reasoning_call_cases": sorted({r["case"] for r in rs if r["no_reasoning_call"] == "True"}),
                    "tplcheck": (sum(r["reasoning_in_prompt"] == "True" for r in tpl.get((cfg,), [])), len(tpl.get((cfg,), [])))}
    return out


def quality(results):
    out = {}
    for (cfg, run), rs in group(rows(results, "quality_runs.csv"), "config", "run").items():
        rev = [r for r in rs if r["kind"] == "review"]
        std = [r for r in rev if r["taskset"] == "tasks"]; hard = [r for r in rev if r["taskset"] == "tasks_hard"]
        out[(cfg, int(run))] = {
            "std_found": (sum(int(r["planted_found"]) for r in std), sum(int(r["planted_total"]) for r in std)),
            "std_fp": sum(int(r["auto_false_positives"]) for r in std),
            "hard_found": (sum(int(r["planted_found"]) for r in hard), sum(int(r["planted_total"]) for r in hard)),
            "hard_fp": sum(int(r["auto_false_positives"]) for r in hard),
            "answers": len(rs), "not_stop": sum(r["finish_reason"] != "stop" for r in rs),
            "wall_review": round(st.median(num(r["wall_s"]) for r in rev)),
            "wall_explore": round(st.median(num(r["wall_s"]) for r in rs if r["kind"] == "explore"))}
    return out


def agentic(results):
    rs = rows(results, "agentic_runs.csv")
    out = {"runs": [(r["config"], r["task"], int(r["run"]), r["end_reason"], int(r["steps"]), num(r["wall_s"]),
                     f'{r["hidden_passed"]}/{r["hidden_total"]}') for r in rs]}
    for (cfg,), g in group(rs, "config").items():
        solved = sum(r["hidden_pass"] == "True" for r in g)
        wall = sum(num(r["wall_s"]) for r in g)
        out[cfg] = {"solved": solved, "wall_s": wall, "solved_per_hour": round(solved / (wall / 3600), 2)}
    return out


def memory(results):
    return {r["config"]: (num(r["peak_gtt_plus_vram_gib"]), num(r["min_mem_available_gib"]))
            for r in rows(results, "memory_peaks.csv")}


def greedy(results):
    return {(r["comparison"], r["config"], int(r["prompt"])): (r["identical_to_control"] == "True", int(r["common_prefix_chars"]),
                                                             int(r["control_chars"]), int(r["chars"]))
            for r in rows(results, "greedy.csv")}


def grades(results):
    return json.loads((Path(results) / "blind" / "grades_by_config.json").read_text())


def deployment(results):
    rs = rows(results, "deployment_check_speed.csv")
    tl = rows(results, "deployment_check_toolsmoke.csv")
    return {"tg": [num(r["tg_tok_s"]) for r in rs], "tg_median": st.median(num(r["tg_tok_s"]) for r in rs),
            "acc": [round(int(r["draft_accepted"]) / int(r["draft_n"]) * 100) for r in rs],
            "pp": (min(num(r["pp_tok_s"]) for r in rs), max(num(r["pp_tok_s"]) for r in rs)),
            "tools": (sum(r["ok"] == "True" for r in tl), len(tl))}


def main():
    R = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "results"
    m = speed_matrix(R)
    print("## Decode tok/s, median (min-max), n=5\n")
    print("| config | " + " | ".join(WORKLOADS) + " |\n|---" * 1 + "|---" * len(WORKLOADS) + "|")
    for c in ORDER:
        print(f"| {c} | " + " | ".join(f"{m[(c, w)]['tg_median']:.2f} ({m[(c, w)]['tg_min']:.1f}-{m[(c, w)]['tg_max']:.1f})"
                                       for w in WORKLOADS) + " |")
    print("\n## Speed-up of the median over g-a1\n")
    for c in ORDER[1:]:
        sp = {w: m[(c, w)]["tg_median"] / m[("g-a1", w)]["tg_median"] for w in WORKLOADS}
        print(f"- {c}: " + ", ".join(f"{w} {v:.2f}x" for w, v in sp.items()))
    print("\n## Prefill tok/s / TTFT s, medians\n")
    for c in ORDER:
        print(f"- {c}: " + ", ".join(f"{w} {m[(c, w)]['pp_median']:.0f}/{m[(c, w)]['ttft_median']:.1f}"
                                     for w in ["review512", "review8k", "review16k", "review32k", "review64k", "warm16k"]))
    print("\n## Draft acceptance (accepted/drafted)\n")
    for c in ("g-df7", "g-combo1"):
        print(f"- {c}: " + ", ".join(f"{w} {m[(c, w)]['draft_acc'] / m[(c, w)]['draft_n']:.0%} ({m[(c, w)]['draft_acc']}/{m[(c, w)]['draft_n']})"
                                     for w in WORKLOADS[:6]))
    print(f"\n## Matrix health\n\n{matrix_health(R)}")
    print("\n## Screen (median of 2)\n")
    s = screen(R)
    for c in sorted({k[0] for k in s}):
        print(f"- {c}: " + ", ".join(f"{w} {s[(c, w)]:.2f}" for w in ("review512", "reason512", "review32k") if (c, w) in s))
    print("\n## Passkey (pass/total, max prompt tokens)\n")
    for c, v in sorted(passkey(R).items()):
        print(f"- {c}: {v[0]}/{v[1]}, max prompt_n {v[2]}")
    print("\n## Tools\n")
    for c, v in sorted(tools(R).items()):
        print(f"- {c}: {v}")
    print("\n## Review/explore (harness auto-scorer)\n")
    for k, v in sorted(quality(R).items()):
        print(f"- {k}: {v}")
    print("\n## Hard agentic tasks (900 s cap)\n")
    a = agentic(R)
    for r in a.pop("runs"):
        print(f"- {r}")
    for c, v in sorted(a.items()):
        print(f"- {c}: {v}")
    print("\n## Memory (peak GTT+VRAM GiB, min MemAvailable GiB)\n")
    for c, v in memory(R).items():
        print(f"- {c}: {v}")
    print("\n## Greedy comparison (identical, common prefix chars, control chars, chars)\n")
    for k, v in greedy(R).items():
        print(f"- {k}: {v}")
    print("\n## Blind grades\n")
    g = grades(R)
    for c, v in g.items():
        print(f"- {c}: {v}")
    base = next(v["cgu_mean"] for c, v in g.items() if c.startswith("baseline"))
    print("- gap to baseline (C,G,U mean): " + ", ".join(f"{c} {v['cgu_mean'] - base:+.2f}" for c, v in g.items()
                                                          if not c.startswith("baseline")))
    print(f"\n## Deployment check\n\n{deployment(R)}")


if __name__ == "__main__":
    main()
