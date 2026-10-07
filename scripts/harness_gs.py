#!/usr/bin/env python3
"""Local-model quality eval harness: agentic coding, review, explore tasks.

Usage: harness_gs.py --models g-df7 --kinds review,explore [--taskset tasks_hard] [--tasks r1_report_cache,...]
Appends one JSON record per (model, task, run) to runs/runs.jsonl (GS_RESULTS_DIR).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(os.environ.get("GS_EVAL_ROOT", Path(__file__).resolve().parent.parent))  # holds tasks/ and tasks_hard/
TASKS = ROOT / "tasks"
RESULTS = Path(os.environ.get("GS_RESULTS_DIR", ROOT / "runs"))
PY = os.environ.get("GS_PYTHON", sys.executable)  # interpreter with pytest, used to run the agentic tasks' tests
WORK = Path(os.environ.get("EVAL_WORK", Path(tempfile.gettempdir()) / "model-eval-work"))
GS_BASE = os.environ.get("GS_BASE", "http://localhost:8080")  # server for the g-* candidates
GS_BASELINE_BASE = os.environ.get("GS_BASELINE_BASE", GS_BASE)  # server for the baseline profile

MODELS = {
    # Meta Muse Glimmer 30B (dense), unsloth Q8_0, Vulkan, no speculative decoding. Its ATEM template re-renders
    # reasoning_content (to=self) between tool steps; reasoning strength = template default "high".
    "muse-glimmer-30b": dict(base=f"{GS_BASELINE_BASE}/v1", sampling=dict(temperature=1.0, top_p=0.95, top_k=64),
                             max_tokens=12000, keep_reasoning=True),
    # Glimmer speed programme (2026-09-28): candidates served by a TEMPORARY llama-swap; identical sampling.
    **{f"g-{c}": dict(base=f"{GS_BASE}/v1", sampling=dict(temperature=1.0, top_p=0.95, top_k=64),
                      max_tokens=12000, keep_reasoning=True)
       for c in ["a0", "a1", "b", "c", "df3", "df7", "df15", "q4dyn", "q5", "q6", "combo1", "combo2"]},
}

MAX_STEPS = 25
WALL_CAP = int(os.environ.get("EVAL_WALL_CAP", 15 * 60))  # env override only for labelled supplementary runs
KEEP_RECENT_TOOL_OUTPUTS = 8

AGENT_SYSTEM = (
    "You are an autonomous coding agent working inside a small Python repository. "
    "Use the provided tools to inspect files, edit code and run the test suite. "
    "Existing test files are read-only: fix the code, not the tests. "
    "Work efficiently. When the task is complete and the tests pass, reply with a brief "
    "summary of what you changed and do not call any more tools."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "list_files", "description": "List files in the repository (recursively) under a directory.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Directory relative to repo root; default '.'"}}}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a UTF-8 text file from the repository.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path relative to repo root"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a file with the given full content.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "apply_edit",
        "description": "Replace exactly one occurrence of old_text with new_text in a file. old_text must match the file exactly and be unique.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
            "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run the pytest suite (tests/ by default) and return its output.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Optional test file or directory, default 'tests'"}}}}},
]


# ----------------------------------------------------------------------------- API

def chat(model, messages, tools=None, timeout=900):
    cfg = MODELS[model]
    body = {"model": cfg.get("api_model", model), "messages": messages, "max_tokens": cfg["max_tokens"], **cfg["sampling"]}
    if tools:
        body["tools"] = tools
    t0 = time.time()
    r = requests.post(cfg["base"] + "/chat/completions", json=body, timeout=timeout)
    latency = time.time() - t0
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    if "choices" not in data or not data["choices"]:
        raise RuntimeError(f"bad response: {str(data)[:500]}")
    return data, latency


# ----------------------------------------------------------------------------- pytest helpers

def run_pytest(repo, targets, junit=None, timeout=120):
    cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", *targets]
    if junit:
        cmd.append(f"--junitxml={junit}")
    try:
        p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"")
        out = out.decode() if isinstance(out, bytes) else out
        return -9, out + f"\n[pytest killed after {timeout}s timeout]"


def junit_counts(path):
    try:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        tot = fail = err = skip = 0
        for s in suites:
            tot += int(s.get("tests", 0)); fail += int(s.get("failures", 0))
            err += int(s.get("errors", 0)); skip += int(s.get("skipped", 0))
        return {"total": tot, "passed": tot - fail - err - skip, "failed": fail + err, "skipped": skip}
    except Exception as e:  # collection crash / timeout
        return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "error": str(e)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- agentic

class Sandbox:
    def __init__(self, repo, protected):
        self.repo = repo.resolve()
        self.protected = protected  # rel path -> hash

    def _resolve(self, rel):
        rel = (rel or ".").strip()
        p = (self.repo / rel).resolve()
        if p != self.repo and self.repo not in p.parents:
            raise ValueError(f"path escapes repository: {rel}")
        return p

    def _relp(self, p):
        return str(p.relative_to(self.repo))

    def list_files(self, path="."):
        base = self._resolve(path)
        if not base.is_dir():
            return f"ERROR: not a directory: {path}"
        out = []
        for f in sorted(base.rglob("*")):
            if any(part in ("__pycache__", ".pytest_cache") for part in f.parts):
                continue
            if f.is_file():
                out.append(self._relp(f))
        return "\n".join(out) or "(empty)"

    def read_file(self, path):
        p = self._resolve(path)
        if not p.is_file():
            return f"ERROR: file not found: {path}"
        txt = p.read_text(errors="replace")
        if len(txt) > 20000:
            txt = txt[:20000] + "\n...[truncated]"
        return txt

    def _check_writable(self, p):
        rel = self._relp(p)
        if rel in self.protected:
            return f"ERROR: {rel} is a protected existing test/config file and is read-only. Fix the code, not the tests."
        return None

    def write_file(self, path, content):
        p = self._resolve(path)
        err = self._check_writable(p)
        if err:
            return err
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {self._relp(p)} ({len(content)} chars)"

    def apply_edit(self, path, old_text, new_text):
        p = self._resolve(path)
        if not p.is_file():
            return f"ERROR: file not found: {path}"
        err = self._check_writable(p)
        if err:
            return err
        txt = p.read_text()
        n = txt.count(old_text)
        if n == 0:
            return "ERROR: old_text not found in file (it must match exactly, including whitespace)"
        if n > 1:
            return f"ERROR: old_text occurs {n} times; make it unique"
        p.write_text(txt.replace(old_text, new_text, 1))
        return f"edited {self._relp(p)}"

    def run_tests(self, path="tests"):
        p = self._resolve(path or "tests")
        rc, out = run_pytest(self.repo, [self._relp(p) if p != self.repo else "."], timeout=90)
        if len(out) > 6000:
            out = "...[earlier output truncated]\n" + out[-6000:]
        return f"exit code {rc}\n{out}", rc == 0


def compact(messages):
    """Elide old tool outputs (same policy for all models) to bound context."""
    idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    for i in idx[:-KEEP_RECENT_TOOL_OUTPUTS]:
        c = messages[i]["content"]
        if len(c) > 600 and not c.endswith("[older tool output elided]"):
            messages[i]["content"] = c[:300] + "\n...[older tool output elided]"


def run_agentic(model, task_dir, run_idx):
    task = json.loads((task_dir / "task.json").read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f"{task['name']}_{model.replace(':', '_')}_r{run_idx}_", dir=WORK))
    repo = work / "repo"
    shutil.copytree(task_dir / "repo", repo)
    protected = {str(f.relative_to(repo)): sha(f) for f in repo.rglob("*")
                 if f.is_file() and (f.parts[len(repo.parts)] == "tests" or f.name in ("pytest.ini", "conftest.py"))
                 or (f.is_file() and f.suffix in (".ini",) and "examples" in f.parts)}
    sb = Sandbox(repo, protected)
    messages = [{"role": "system", "content": AGENT_SYSTEM},
                {"role": "user", "content": task["prompt"] + "\n\nThe repository root is the working directory; use relative paths."}]
    st = dict(steps=0, tool_calls=0, tool_errors=0, malformed_calls=0, unknown_tool=0, repeated_calls=0,
              nudges=0, prompt_tokens=0, completion_tokens=0, test_runs=0, protected_write_attempts=0,
              length_truncations=0, api_errors=0)
    calls = []
    t0 = time.time()
    end_reason = None
    last_tests_ok = False
    prev_sig, streak = None, 0
    while True:
        if st["steps"] >= MAX_STEPS:
            end_reason = "max_steps"; break
        elapsed = time.time() - t0
        if elapsed > WALL_CAP:
            end_reason = "wall_cap"; break
        compact(messages)
        try:
            data, lat = chat(model, messages, TOOLS, timeout=max(60, WALL_CAP - elapsed + 30))
        except Exception as e:
            st["api_errors"] += 1
            calls.append({"step": st["steps"], "error": repr(e)[:800]})
            end_reason = "api_timeout" if "Timeout" in repr(e) or "timed out" in repr(e) else "api_error"
            break
        st["steps"] += 1
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {}) or {}
        st["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
        st["completion_tokens"] += usage.get("completion_tokens", 0) or 0
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        tcs = msg.get("tool_calls") or []
        rec = {"step": st["steps"], "latency_s": round(lat, 2), "finish_reason": choice.get("finish_reason"),
               "usage": usage, "content": content, "reasoning_chars": len(reasoning),
               "reasoning_head": reasoning[:1500], "tool_calls": tcs, "timings": data.get("timings")}
        calls.append(rec)
        if choice.get("finish_reason") == "length":
            st["length_truncations"] += 1
        if not tcs:
            if re.search(r"<tool_call>|<function=|\"name\"\s*:\s*\"(read_file|write_file|apply_edit|run_tests|list_files)\"", content):
                st["malformed_calls"] += 1
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Your tool call could not be parsed. Call tools using the function-calling interface."})
                continue
            messages.append({"role": "assistant", "content": content})
            if not last_tests_ok and st["nudges"] < 1:
                st["nudges"] += 1
                messages.append({"role": "user", "content":
                                 "The test suite has not passed in your most recent run_tests call. Continue working until it passes, or reply DONE if you are giving up."})
                continue
            end_reason = "model_finished" if last_tests_ok else "model_stopped_tests_not_green"
            break
        amsg = {"role": "assistant", "content": content, "tool_calls": tcs}
        if MODELS[model].get("keep_reasoning") and reasoning:
            amsg["reasoning_content"] = reasoning
        messages.append(amsg)
        for tc in tcs:
            st["tool_calls"] += 1
            fn = tc.get("function", {})
            name, raw = fn.get("name"), fn.get("arguments") or "{}"
            tc_id = tc.get("id") or uuid.uuid4().hex[:12]
            tc["id"] = tc_id
            sig = (name, raw)
            streak = streak + 1 if sig == prev_sig else 1
            prev_sig = sig
            if streak >= 3:
                st["repeated_calls"] += 1
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
            except Exception as e:
                st["malformed_calls"] += 1; st["tool_errors"] += 1
                result = f"ERROR: tool arguments were not valid JSON: {e}"
            else:
                try:
                    if name == "run_tests":
                        st["test_runs"] += 1
                        result, last_tests_ok = sb.run_tests(args.get("path", "tests"))
                    elif name in ("list_files", "read_file", "write_file", "apply_edit"):
                        result = getattr(sb, name)(**args)
                        if name in ("write_file", "apply_edit") and not result.startswith("ERROR"):
                            last_tests_ok = False
                    else:
                        st["unknown_tool"] += 1
                        result = f"ERROR: unknown tool {name!r}"
                except (TypeError, ValueError) as e:  # ValueError: path outside the repo (added 2026-09-28)
                    result = f"ERROR: bad arguments for {name}: {e}"
                if result.startswith("ERROR"):
                    st["tool_errors"] += 1
                    if "protected" in result:
                        st["protected_write_attempts"] += 1
            messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})
            rec.setdefault("tool_results", []).append(result[:1500])
    wall = time.time() - t0

    # ---------------- final scoring
    tampered = []
    for rel, h in protected.items():
        f = repo / rel
        if not f.exists() or sha(f) != h:
            tampered.append(rel)
            f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(task_dir / "repo" / rel, f)
    vis_xml = work / "visible.xml"
    run_pytest(repo, [r for r in protected if r.startswith("tests/") and r.endswith(".py") and Path(r).name.startswith("test_")],
               junit=vis_xml)
    visible = junit_counts(vis_xml)
    hidden_files = []
    for hf in sorted((task_dir / "hidden").glob("*.py")):
        shutil.copy2(hf, repo / "tests" / hf.name)
        hidden_files.append("tests/" + hf.name)
    hid_xml = work / "hidden.xml"
    rc, hid_out = run_pytest(repo, hidden_files, junit=hid_xml)
    hidden = junit_counts(hid_xml)
    full_xml = work / "full.xml"
    run_pytest(repo, ["tests"], junit=full_xml)
    full = junit_counts(full_xml)
    diff = subprocess.run(["diff", "-ruN", "-x", "__pycache__", "-x", "test_hidden_*", str(task_dir / "repo"), str(repo)],
                          capture_output=True, text=True).stdout
    return {
        "kind": "agentic", "task": task["name"], "category": task["category"], "model": model, "run": run_idx,
        "end_reason": end_reason, "wall_s": round(wall, 1), **st,
        "visible": visible, "hidden": hidden, "full_suite": full, "tampered": tampered,
        "visible_pass": visible["total"] > 0 and visible["failed"] == 0,
        "hidden_pass": hidden["total"] > 0 and hidden["failed"] == 0,
        "hidden_output_tail": hid_out[-2500:],
        "final_diff": diff[:20000], "transcript": calls, "workdir": str(work),
    }


# ----------------------------------------------------------------------------- single-shot tasks

REVIEW_PROMPT = """You are reviewing a pull request. Context: {context}

Review the diff below for real defects: bugs, security problems, and behavior regressions. Do not report pure style preferences.

Output format: a numbered list, one issue per item, each formatted as
`N. [severity: high|medium|low] <file>:<line or function> - <what is wrong and why it matters> - <suggested fix>`
Report only issues you are confident are real; if there are none, say "No issues found."

```diff
{diff}
```"""


def build_single_prompt(kind, name):
    if kind == "review":
        rub = json.loads((TASKS / "review" / "rubric.json").read_text())[name]
        diff = (TASKS / "review" / rub["file"]).read_text()
        return REVIEW_PROMPT.format(context=rub["context"], diff=diff)
    d = TASKS / "explore" / name
    task = json.loads((d / "task.json").read_text())
    parts = [task["question"], ""]
    if task.get("files"):  # cited-explore tasks: sources shown with line numbers
        for rel in task["files"]:
            lines = (d / "src" / rel).read_text().splitlines()
            numbered = "\n".join(f"{i:4d}| {ln}" for i, ln in enumerate(lines, 1))
            parts.append(f"### {rel}\n```python\n{numbered}\n```\n")
        return "\n".join(parts)
    if name == "e1_retry":
        for f in sorted((d / "src").rglob("*")):
            if f.is_file():
                lang = "python" if f.suffix == ".py" else "markdown"
                parts.append(f"### {f.relative_to(d / 'src')}\n```{lang}\n{f.read_text()}```\n")
    elif name == "e2_log":
        parts.append("```\n" + (d / "service.log").read_text() + "```")
    elif name == "e3_varint":
        parts.append("```python\n" + (d / "snippet.py").read_text() + "```")
    elif name == "e4_design":
        parts.append((d / "design.md").read_text())
    return "\n".join(parts)


def run_single(model, kind, name):
    prompt = build_single_prompt(kind, name)
    messages = [{"role": "user", "content": prompt}]
    t0 = time.time()
    rec = {"kind": kind, "task": name, "model": model, "run": 1, "prompt": prompt}
    try:
        data, lat = chat(model, messages, timeout=1200)
        choice = data["choices"][0]
        msg = choice["message"]
        rec.update(answer=msg.get("content") or "", reasoning_chars=len(msg.get("reasoning_content") or ""),
                   finish_reason=choice.get("finish_reason"), usage=data.get("usage"), timings=data.get("timings"),
                   error=None)
    except Exception as e:
        rec.update(answer="", error=repr(e)[:800])
    rec["wall_s"] = round(time.time() - t0, 1)
    if kind == "review":
        rec["review_score"] = score_review(name, rec["answer"])
    return rec


def split_items(text):
    items, cur = [], None
    for line in text.splitlines():
        if re.match(r"^\s*(\d+[.)]|[-*•])\s+\S", line) and not re.match(r"^\s{4,}[-*]", line):
            if cur is not None:
                items.append(cur)
            cur = line
        elif cur is not None and line.strip():
            cur += "\n" + line
    if cur is not None:
        items.append(cur)
    return items


def score_review(name, answer):
    rub = json.loads((TASKS / "review" / "rubric.json").read_text())[name]
    items = split_items(answer)
    found = {b["id"]: None for b in rub["planted"]}
    unmatched = []
    for i, it in enumerate(items):
        low = it.lower()
        hit = False
        for b in rub["planted"]:
            if all(re.search("|".join(g), low) for g in b["match_any"]):
                if found[b["id"]] is None:
                    found[b["id"]] = i
                hit = True
        if not hit:
            acceptable = any(re.search(a, low) for a in rub["acceptable"])
            sev = re.search(r"\[\s*(?:severity:\s*)?(high|medium|low)\s*\]|severity:\s*(high|medium|low)", low)
            unmatched.append({"item": i, "acceptable": acceptable, "severity": (sev.group(1) or sev.group(2)) if sev else None,
                              "text": it[:400]})
    return {"n_items": len(items), "found": found,
            "recall": sum(v is not None for v in found.values()) / len(found),
            "false_positives": sum(not u["acceptable"] for u in unmatched),
            "unmatched": unmatched}


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--kinds", default="agentic,review,explore")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--run-start", type=int, default=1)
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--out", default=str(RESULTS / "runs.jsonl"))
    ap.add_argument("--taskset", default="tasks", help="task directory under the eval root (tasks | tasks_hard)")
    a = ap.parse_args()
    global TASKS
    TASKS = ROOT / a.taskset
    RESULTS.mkdir(exist_ok=True)
    only = None if a.tasks == "all" else set(a.tasks.split(","))
    kinds = a.kinds.split(",")
    for model in a.models.split(","):
        jobs = []
        if "review" in kinds:
            jobs += [("review", n) for n in sorted(json.loads((TASKS / "review" / "rubric.json").read_text()))]
        if "explore" in kinds:
            jobs += [("explore", d.name) for d in sorted((TASKS / "explore").iterdir()) if d.is_dir()]
        if "agentic" in kinds:
            for r in range(a.run_start, a.run_start + a.runs):
                jobs += [("agentic", d.name, r) for d in sorted((TASKS / "agentic").iterdir()) if d.is_dir()]
        for job in jobs:
            if only and job[1] not in only:
                continue
            t0 = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] {model} {job} ...", flush=True)
            try:
                rec = run_agentic(model, TASKS / "agentic" / job[1], job[2]) if job[0] == "agentic" \
                    else run_single(model, job[0], job[1])
            except Exception as e:
                import traceback
                rec = {"kind": job[0], "task": job[1], "model": model, "run": job[2] if len(job) > 2 else 1,
                       "harness_error": traceback.format_exc()}
            rec["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            rec["taskset"] = a.taskset
            with open(a.out, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            summ = {k: rec.get(k) for k in ("end_reason", "steps", "visible_pass", "hidden_pass", "error", "harness_error")
                    if rec.get(k) is not None}
            if "review_score" in rec:
                summ["recall"] = rec["review_score"]["recall"]; summ["fp"] = rec["review_score"]["false_positives"]
            if "hidden" in rec:
                summ["hidden"] = f"{rec['hidden']['passed']}/{rec['hidden']['total']}"
            print(f"    done in {time.time() - t0:.0f}s {summ}", flush=True)


if __name__ == "__main__":
    main()
