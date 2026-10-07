#!/usr/bin/env python3
"""Export per-run summary metrics from the study's raw outputs into results/*.csv.

The raw outputs (bench/passkey/toolsmoke/greedy/harness JSONL, tplcheck text, the memory log) hold full model
transcripts and host details, so they are not committed. This script keeps only the numeric/outcome fields that the
README's claims rest on. Running it again on your own runs/ directory produces the same files for your hardware.

Usage:
  tools/export_summaries.py --study RUNS_DIR [--baseline-std F --baseline-hard F] --out results/
RUNS_DIR is the directory scripts/*.py wrote into (runs/ by default; the study called it results/).
Baseline files are harness outputs that contain records for --baseline-model (default muse-glimmer-30b).
"""
import argparse
import csv
import json
import re
from pathlib import Path

BASELINE_LABEL = "baseline-q8"


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in p.open() if l.strip()] if p.exists() else []


def write_csv(path, rows, cols):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"{path}: {len(rows)} rows")


def other_models(r):
    """Models loaded on the other server (GS_PROD_BASE); "ERR ..." entries mean that server did not answer."""
    return sum(1 for m in r.get("prod_running") or [] if not str(m).startswith("ERR"))


BENCH_COLS = ["source", "config", "rep", "workload", "error", "finish", "prompt_n", "cache_n", "ttft_s", "pp_tok_s", "gen_n",
              "tg_tok_s", "draft_n", "draft_accepted", "total_s", "reasoning_chars", "content_chars", "rep_score",
              "mem_avail_gib_after", "swap_used_gib_after", "concurrent_server_models"]


def bench_rows(recs, source):
    out = []
    for r in recs:
        out.append({"source": source, "config": r["model"], "rep": r["rep"], "workload": r["workload"], "error": r.get("error") or "",
                    "finish": r.get("finish"), "prompt_n": r.get("prompt_n"), "cache_n": r.get("cache_n"),
                    "ttft_s": r.get("ttft"), "pp_tok_s": r.get("pp"), "gen_n": r.get("gen_n"),
                    "tg_tok_s": r.get("tg"), "draft_n": r.get("draft_n"), "draft_accepted": r.get("draft_acc"),
                    "total_s": r.get("total_s"), "reasoning_chars": r.get("reasoning_chars"),
                    "content_chars": r.get("content_chars"), "rep_score": r.get("rep_score"),
                    "mem_avail_gib_after": r["mem_after"]["mem_avail_gib"],
                    "swap_used_gib_after": r["mem_after"]["swap_used_gib"],
                    # count only: the names of whatever else the host was serving are not part of the result
                    "concurrent_server_models": other_models(r)})
    return out


PASSKEY_COLS = ["config", "depth", "place", "rep", "ok", "finish", "error", "prompt_n", "cache_n", "pp_tok_s", "tg_tok_s",
                "gen_n", "total_s", "draft_n", "draft_accepted", "rep_score", "concurrent_server_models"]


def passkey_rows(recs):
    return [{"config": r["model"], "depth": r["depth"], "place": r["place"], "rep": r["rep"], "ok": r["ok"],
             "finish": r.get("finish"), "error": r.get("error") or "", "prompt_n": r.get("prompt_n"),
             "cache_n": r.get("cache_n"), "pp_tok_s": r.get("pp"), "tg_tok_s": r.get("tg"),
             "gen_n": r.get("gen_n"), "total_s": r.get("total_s"), "draft_n": r.get("draft_n"),
             "draft_accepted": r.get("draft_acc"), "rep_score": r.get("rep_score"),
             "concurrent_server_models": other_models(r)} for r in recs]


TOOL_COLS = ["config", "case", "stream", "ok", "problems", "latency_s", "finish", "n_calls", "reasoning_chars",
             "tool_call_first", "no_reasoning_call"]


def tool_rows(recs, config=None):
    # tool_call_first: set only on the added first_* cases (no reasoning before the call).
    # no_reasoning_call: any record with a call and zero reasoning; this is what summarize.py counted as
    # "true tool-call-first", and in the study those records were all history cases (hist_*), not first_*.
    return [{"config": config or r["model"], "case": r["case"], "stream": r["stream"], "ok": r["ok"],
             "problems": "; ".join(r.get("problems") or []), "latency_s": r.get("latency_s"), "finish": r.get("finish"),
             "n_calls": len(r.get("calls") or []), "reasoning_chars": r.get("reasoning_chars"),
             "tool_call_first": r.get("tool_call_first", ""),
             "no_reasoning_call": bool(r.get("calls")) and r.get("reasoning_chars") == 0} for r in recs]


TPL_LINE = re.compile(r"^\[(.+)\] reasoning in prompt: (True|False)$")


def tplcheck_rows(path, config):
    return [{"config": config, "case": m.group(1), "reasoning_in_prompt": m.group(2) == "True"}
            for m in (TPL_LINE.match(l) for l in Path(path).read_text().splitlines()) if m]


def common_prefix(a, b):
    return next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))


def greedy_rows(ctl_recs, runs):
    """Compare each greedy run with the control's first run (first records of ctl_recs per prompt)."""
    ctl = {}
    for r in ctl_recs:
        ctl.setdefault(r["prompt"], (r.get("reasoning") or "") + (r.get("content") or ""))
    out = []
    for label, recs in runs:
        for r in recs:
            text = (r.get("reasoning") or "") + (r.get("content") or "")
            a = ctl[r["prompt"]]
            out.append({"comparison": label, "config": r["model"], "prompt": r["prompt"], "error": r.get("error") or "",
                        "tg_tok_s": r.get("tg"), "draft_n": r.get("draft_n"), "draft_accepted": r.get("draft_acc"),
                        "chars": len(text), "control_chars": len(a), "identical_to_control": text == a,
                        "common_prefix_chars": common_prefix(a, text)})
    return out


def quality_rows(recs, config, run, taskset):
    out = []
    for r in recs:
        if r.get("kind") not in ("review", "explore"):
            continue
        sc = r.get("review_score") or {}
        found = sc.get("found") or {}
        out.append({"config": config, "run": run, "taskset": r.get("taskset", taskset), "kind": r["kind"],
                    "task": r["task"], "error": r.get("error") or ("harness_error" if "harness_error" in r else ""),
                    "finish_reason": r.get("finish_reason"), "wall_s": r.get("wall_s"),
                    "completion_tokens": (r.get("usage") or {}).get("completion_tokens"),
                    "reasoning_chars": r.get("reasoning_chars"), "answer_chars": len(r.get("answer") or ""),
                    "tg_tok_s": (r.get("timings") or {}).get("predicted_per_second"),
                    "planted_found": sum(v is not None for v in found.values()) if sc else "",
                    "planted_total": len(found) if sc else "",
                    "auto_false_positives": sc.get("false_positives", "") if sc else ""})
    return out


def agentic_rows(recs, config):
    return [{"config": config, "task": r["task"], "run": r["run"], "end_reason": r.get("end_reason"),
             "steps": r.get("steps"), "wall_s": r.get("wall_s"), "tool_calls": r.get("tool_calls"),
             "tool_errors": r.get("tool_errors"), "malformed_calls": r.get("malformed_calls"),
             "api_errors": r.get("api_errors"), "tampered_files": len(r.get("tampered") or []),
             "visible_pass": r.get("visible_pass"), "hidden_passed": (r.get("hidden") or {}).get("passed"),
             "hidden_total": (r.get("hidden") or {}).get("total"), "hidden_pass": r.get("hidden_pass")}
            for r in recs if r.get("kind") == "agentic"]


MEM_LINE = re.compile(r"^(\S+) avail=([\d.]+)GiB swap_used=([\d.]+)GiB gtt=([\d.]+)GiB vram=([\d.]+)GiB prod=\[(.*)\] test=\[(.*)\]$")


def memory_rows(path):
    """Per-minute samples where exactly one candidate was ready on the test server."""
    per, prod_loaded, n = {}, 0, 0
    for line in Path(path).read_text().splitlines():
        m = MEM_LINE.match(line)
        if not m:
            continue
        n += 1
        prod_loaded += bool(m.group(6))
        test = [t for t in m.group(7).split(",") if t]
        if len(test) != 1 or not test[0].endswith(":ready"):
            continue
        cfg = test[0].rsplit(":", 1)[0]
        d = per.setdefault(cfg, {"config": cfg, "samples": 0, "peak_gtt_plus_vram_gib": 0.0, "min_mem_available_gib": 1e9,
                                 "max_swap_used_gib": 0.0})
        d["samples"] += 1
        d["peak_gtt_plus_vram_gib"] = max(d["peak_gtt_plus_vram_gib"], round(float(m.group(4)) + float(m.group(5)), 1))
        d["min_mem_available_gib"] = min(d["min_mem_available_gib"], float(m.group(2)))
        d["max_swap_used_gib"] = max(d["max_swap_used_gib"], float(m.group(3)))
    print(f"memory log: {n} samples, {prod_loaded} with a model loaded on the other server")
    return list(per.values()), {"samples": n, "samples_with_other_server_model_loaded": prod_loaded}


VERIFY_LINE = re.compile(r"^(review\d+): prompt_n=(\d+) pp=([\d.]+) gen_n=(\d+) tg=([\d.]+) tok/s draft=(\d+)/(\d+) finish=(\w+) err=(.*)$")


def verify_rows(path):
    """Post-deployment speed check (plain-text log of three ~450-token review prompts)."""
    return [{"prompt": m.group(1), "prompt_n": int(m.group(2)), "pp_tok_s": float(m.group(3)), "gen_n": int(m.group(4)),
             "tg_tok_s": float(m.group(5)), "draft_accepted": int(m.group(6)), "draft_n": int(m.group(7)),
             "finish": m.group(8), "error": "" if m.group(9) == "None" else m.group(9)}
            for m in (VERIFY_LINE.match(l) for l in Path(path).read_text().splitlines()) if m]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--study", required=True, help="directory with the raw outputs of scripts/*.py")
    ap.add_argument("--baseline-std", help="harness output with baseline standard-set review/explore records")
    ap.add_argument("--baseline-hard", help="harness output with baseline hard-set review/explore/agentic records")
    ap.add_argument("--baseline-model", default="muse-glimmer-30b")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    S, O = Path(a.study), Path(a.out)
    O.mkdir(parents=True, exist_ok=True)

    write_csv(O / "screen.csv", bench_rows(jl(S / "screen.jsonl"), "screen") + bench_rows(jl(S / "screen_combo.jsonl"), "screen_combo"), BENCH_COLS)
    write_csv(O / "speed_matrix.csv", bench_rows(jl(S / "matrix.jsonl"), "matrix"), BENCH_COLS)
    write_csv(O / "postreboot_check.csv", bench_rows(jl(S / "postreboot_check.jsonl"), "postreboot_check"), BENCH_COLS)

    pk = []
    for f in sorted(S.glob("passkey_*.jsonl")):
        if "interrupted" not in f.name:
            pk += passkey_rows(jl(f))
    write_csv(O / "passkey.csv", pk, PASSKEY_COLS)
    write_csv(O / "passkey_reboot_interrupted.csv", passkey_rows(jl(S / "passkey_g-df7_reboot_interrupted.jsonl")),
              PASSKEY_COLS)

    tools, tpl = [], []
    for f in sorted(S.glob("toolsmoke_g-*.jsonl")):
        tools += tool_rows(jl(f))
    for f in sorted(S.glob("tplcheck_g-*.txt")):
        tpl += tplcheck_rows(f, f.stem.removeprefix("tplcheck_"))
    write_csv(O / "toolsmoke.csv", tools, TOOL_COLS)
    write_csv(O / "tplcheck.csv", tpl, ["config", "case", "reasoning_in_prompt"])

    greedy = jl(S / "greedy.jsonl")
    ctl = [r for r in greedy if r["model"] == "g-a1"]
    write_csv(O / "greedy.csv", greedy_rows(ctl, [("vs g-a1 run 1", greedy),
                                                   ("g-a1 run 2 vs g-a1 run 1", jl(S / "greedy_a1_repeat.jsonl"))]),
              ["comparison", "config", "prompt", "error", "tg_tok_s", "draft_n", "draft_accepted", "chars",
               "control_chars", "identical_to_control", "common_prefix_chars"])

    q = []
    if a.baseline_std:
        q += quality_rows([r for r in jl(a.baseline_std) if r["model"] == a.baseline_model], BASELINE_LABEL, 1, "tasks")
    if a.baseline_hard:
        q += quality_rows([r for r in jl(a.baseline_hard) if r["model"] == a.baseline_model], BASELINE_LABEL, 1, "tasks_hard")
    for f in sorted(S.glob("q_g-*_r[0-9].jsonl")):
        m = re.match(r"q_(g-[\w]+)_(std|hard)_r(\d)", f.stem)
        q += quality_rows(jl(f), m.group(1), int(m.group(3)), "tasks" if m.group(2) == "std" else "tasks_hard")
    write_csv(O / "quality_runs.csv", q, ["config", "run", "taskset", "kind", "task", "error", "finish_reason", "wall_s",
                                          "completion_tokens", "reasoning_chars", "answer_chars", "tg_tok_s",
                                          "planted_found", "planted_total", "auto_false_positives"])

    ag = []
    if a.baseline_hard:
        ag += agentic_rows([r for r in jl(a.baseline_hard) if r["model"] == a.baseline_model], BASELINE_LABEL)
    for f in sorted(S.glob("agentic_g-*.jsonl")):
        ag += agentic_rows(jl(f), f.stem.removeprefix("agentic_"))
    write_csv(O / "agentic_runs.csv", ag, ["config", "task", "run", "end_reason", "steps", "wall_s", "tool_calls",
                                           "tool_errors", "malformed_calls", "api_errors", "tampered_files",
                                           "visible_pass", "hidden_passed", "hidden_total", "hidden_pass"])

    if (S / "prod_verify_speed.txt").exists():  # deployment check of the chosen config (Q8 + DFlash n7), 2026-09-29
        write_csv(O / "deployment_check_speed.csv", verify_rows(S / "prod_verify_speed.txt"),
                  ["prompt", "prompt_n", "pp_tok_s", "gen_n", "tg_tok_s", "draft_accepted", "draft_n", "finish", "error"])
        write_csv(O / "deployment_check_toolsmoke.csv",
                  tool_rows(jl(S / "prod_toolsmoke_dflash.jsonl"), config="deployed Q8 + DF7"), TOOL_COLS)

    if (S / "mem_log.txt").exists():
        rows, totals = memory_rows(S / "mem_log.txt")
        write_csv(O / "memory_peaks.csv", rows, ["config", "samples", "peak_gtt_plus_vram_gib", "min_mem_available_gib",
                                                 "max_swap_used_gib"])
        (O / "memory_log_totals.json").write_text(json.dumps(totals, indent=2) + "\n")


if __name__ == "__main__":
    main()
