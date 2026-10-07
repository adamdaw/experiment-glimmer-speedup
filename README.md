# experiment-glimmer-speedup

Can a local Muse Glimmer 30B run faster than a Q8_0 llama.cpp setup without losing answer quality? This repo
holds the method, the harness, the task inputs and the summary results of a study run on 2026-09-28/29 on one AMD
Strix Halo machine. The aim is that someone else can check the result and re-run the study on their own hardware.

**Short answer.** Adding Meta's DFlash drafter as a speculative decoder (`--spec-draft-n-max 7`, llama.cpp
7ab4ee7ba) to the Q8_0 target raised decode speed by about 2–3.6×. It passed every objective gate. A single blind
grader scored its review/explore answers level with the baseline: 3.79 for DF7 against 3.82 for the baseline, with
Q5 + DF7 at 3.74. The DF7 configuration was deployed on 2026-09-29. Read [Limitations](#limitations) before relying
on the quality side: the grade comes from one grader on 11 tasks.

## Contents

| path | what |
|---|---|
| `scripts/` | The study's scripts, ported: harness, benchmarks, gates, packet builder ([Scripts](#scripts)) |
| `config/llama-swap.test.yaml` | Every configuration compared, as a llama-swap config (paths are placeholders) |
| `config/queue.study.txt` | The study's job list in run order, for `scripts/queue_runner.sh` |
| `tasks/`, `tasks_hard/` | Task inputs the study used: 5 code reviews, 6 explore questions, 2 agentic coding tasks |
| `results/*.csv` | Per-run summary metrics (no transcripts) |
| `results/blind/` | Blind-grading packet, key, grades and per-configuration summary |
| `results/environment/` | Model and binary hashes, GGUF headers, host versions |
| `tools/` | Summary export (`export_summaries.py`), grade de-anonymisation (`blind_summary.py`), README number check (`claims.py`) |
| `tests/` | Tests for the tools and the harness scorer, and checks that pin the headline README numbers to `results/` |

## Question and hypothesis

**Question:** which configuration of Muse Glimmer 30B is faster than the production Q8 profile, with no quality loss?

**Hypothesis:** speculative decoding should give a large decode speed-up at unchanged quality, because the Q8 target
verifies every drafted token. A smaller quantisation might also help, but it changes the target weights, so its
quality has to be measured rather than assumed.

The starting point was a Q8_0 profile decoding at about 7.6 tok/s. At that speed the model was usable for one-off
reviews, but too slow for agentic coding inside a 15-minute cap.

## Method

### Configurations

Every configuration used the same server command. Only the named variable changed:
`-lm none -ngl 999 -fa on --jinja --ctx-size 131072 --parallel 1 --cache-ram 0 --temp 1.0 --top-p 0.95 --top-k 64 --min-p 0.0`.
Reasoning strength was the chat template's default (high), except in the `legacy256` fixture, which uses low.

| id | build | target | speculation |
|---|---|---|---|
| `g-a0` | 7d6f5d02b (the pre-study build) | Q8_0 | none |
| `g-a1` (control) | 7ab4ee7ba | Q8_0 | none |
| `g-b` | 7ab4ee7ba | Q8_0 | ngram-simple, n 12, m 16, draft max 16 |
| `g-c` | 7ab4ee7ba | Q8_0 | ngram-mod, match 24, min 8, max 16 |
| `g-df3` / `g-df7` / `g-df15` | 7ab4ee7ba | Q8_0 | DFlash drafter, `--spec-draft-n-max` 3 / 7 / 15 |
| `g-q4dyn` / `g-q5` / `g-q6` | 7ab4ee7ba | Meta Dynamic Q4_K_XL / Unsloth UD-Q5_K_M / UD-Q6_K_XL | none |
| `g-combo1` | 7ab4ee7ba | UD-Q5_K_M | DFlash, n-max 7 |
| baseline | 7d6f5d02b | Q8_0 | none (the production profile, same command as `g-a0`) |

All DFlash runs used `--spec-type draft-dflash -md dflash-Muse-Glimmer-30B-Q4_K_M.gguf -ngld 999 --spec-draft-p-min 0 -ctkd f16 -ctvd f16`.
The full commands are in `config/llama-swap.test.yaml`.

`g-a0` and `g-a1` were compared first (template rendering, tool calls, speed). They did not differ, so `g-a1` became
the control and every later candidate changed one variable against the same binary.

### Stages

1. **Screen** (`bench_gs.py`, 2 alternating reps). Workloads: review with code quoting (512-token prompt), reasoning
   at high strength (512-token prompt), and a 32K review. Each configuration ran alone.
2. **Full speed matrix** (`bench_gs.py`, 5 reps in alternating order: A1, DF7, Q5, combo1, then reversed).
   Workloads: review512, reason512, review at 8K/16K/32K/64K, a warm 16K prefix (`warm16k`), and the `legacy256`
   fixture (256 tokens, `ignore_eos`, low reasoning). Each prompt got a fresh random nonce, so the prompt cache was
   cold, except `warm16k`, which reuses the preceding 16K prefix.
3. **Correctness gates.**
   - Passkey retrieval (`passkey_gs.py`): Python stdlib source as the haystack, with a 5-digit key at the start,
     middle and end. Depths 2K–64K, plus a "116000" target that reached about 106K prompt tokens; the 8K and 32K
     cases are repeated on the warm slot.
   - Tool calls (`toolsmoke_gs.py`): 14 records from 7 cases × streaming/non-streaming, plus 18 added tool-call-first
     records.
   - Chat-template re-rendering of reasoning between tool steps (`tplcheck_gs.py`).
   - A greedy-decoding comparison (`greedy_gs.py`), as a diagnostic only.
4. **Review/explore quality** (`harness_gs.py`, 2 runs per configuration):
   - **Standard set** (`tasks/`): 3 code-review diffs with 2 planted bugs each, and 4 explore questions (a retry
     library, a service log, a varint decoder, a design doc).
   - **Hard set** (`tasks_hard/`): 2 review diffs with 2 planted bugs each, and 2 "cited explore" questions where
     answers must cite file:line.
   - The harness auto-scores reviews with a regex matcher against `rubric.json`.
5. **Hard agentic tasks** (`harness_gs.py --kinds agentic --taskset tasks_hard`, 2 runs each): `h1_refunds` and
   `h2_schedule_tz`, run under the harness's original limits (900 s wall cap, 25 steps). Hidden tests decide pass or
   fail.
6. **Blind grading** of the review/explore answers (next section).

### Blind grading

- **Packet:** `scripts/build_blind_gs.py` built `results/blind/packet.md`. Each of the 11 tasks has 5 answers: the
  baseline Q8 answer, two runs of Q8 + DF7, and two runs of Q5 + DF7.
  - Labels are shuffled independently per task.
  - Model and vendor names in the answers are replaced with `[model]` (0 replacements were needed).
  - The key, `results/blind/KEY.json`, was kept away from the grader.
- **Baseline answers:** these came from an eval run the day before (2026-09-28) on the production profile, with the
  harness that `harness_gs.py` was copied from.
- **Grader:** one grader, an **OpenAI Codex agent**. Its vendor differs from the graded model's (Meta). The grading
  artefacts do not record the exact Codex model or version.
- **What the grader saw and did:** it had only `packet.md`, and scored each answer 1–5 on correctness,
  groundedness, completeness and concision (the packet's rubric) plus usefulness. It also counted planted bugs
  found, false alarms, and wrong or hallucinated citations. Its output is `results/blind/GRADES.json` and
  `GRADES.md`.
- **De-anonymising:** the study's orchestrator, an AI agent, matched grades to configurations using the key.
  `tools/blind_summary.py` reproduces that step.
- **The composite:** the summary figure used when the study was closed is the mean of correctness, groundedness and
  usefulness per answer, averaged over answers. The source did not document this choice. It is the only
  combination of the five axes that reproduces the quoted 3.82 / 3.79 / 3.74, so the five-axis mean is reported
  next to it.
- **Pass rule (set before grading):** each candidate's mean must not fall below the baseline graded in the same
  packet, with no drop in planted bugs found and no increase in false alarms.

### How speed was measured

Decode (`tg`) and prefill (`pp`) tokens per second, and draft counts, come from llama-server's own `timings` block
on each streamed response. TTFT is measured client-side, up to the first content, reasoning or tool-call delta.
Medians are over reps. Speed-ups are ratios of medians against `g-a1`.

## Environment

- **Hardware:** AMD Strix Halo APU (integrated GPU, gfx1151), 128 GB unified memory, one machine.
- **OS:** a Fedora 44-based distribution. Kernel 7.2.4, then 7.2.7 after a mid-study reboot
  ([Limitations](#limitations)). Mesa RADV 26.2.2. Details are in `results/environment/host_versions.txt`.
- **Backend:** llama.cpp with Vulkan (RADV) only. ROCm was not used.
- **llama.cpp builds:**
  - `7ab4ee7ba`, the merge of PR #29242, 97 commits after `7d6f5d02b`. Built as a Vulkan Release build with
    `-DGGML_NATIVE=ON` inside a community Strix Halo Vulkan/RADV toolbox container. Every candidate used it.
  - `7d6f5d02b` (build 11003): the prebuilt server that the production profile used at the time (`g-a0` and the
    baseline).
  - Binary hashes are in `results/environment/build_hashes.txt`.
- **Serving:** each candidate ran alone behind a temporary [llama-swap](https://github.com/mostlygeek/llama-swap) on
  a loopback port, one model at a time. `results/memory_log_totals.json` shows that none of 1,062 per-minute
  samples had a model loaded on the host's other llama-swap; the speed matrix shows the same (0 of 180 records).
- **Model files** (not redistributed). Both Hugging Face repositories are tagged `license:apache-2.0` (checked
  2026-10-07). Check the model cards for any further terms before you download.

| file | download | bytes | sha256 |
|---|---|---:|---|
| `Muse-Glimmer-30B-Q8_0.gguf` (target) | [unsloth/Muse-Glimmer-30B-GGUF @ faa5b025c584](https://huggingface.co/unsloth/Muse-Glimmer-30B-GGUF/tree/faa5b025c584459c13febfa5c59883516710ae39) | 29,612,957,984 | `f2c087d694ca8242a4a436076df7c041703ab051ac4b72bb1bfe2698299b0e86` ¹ |
| `dflash-Muse-Glimmer-30B-Q4_K_M.gguf` (drafter) | [meta-models/Muse-Glimmer-30B-GGUF @ 70bf1b61ac09](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF/tree/70bf1b61ac09f91b24d39038091b41c582bc5d7a) | 1,631,208,128 | `b2e808bf656086fe86bd0d0bd990f01d33e377537a07c02d45371517c8b264ef` |
| `Muse-Glimmer-30B-UD-Q5_K_M.gguf` | unsloth @ faa5b025c584 | 19,194,274,848 | `27c27bc0cc2591344a9ef977d57aa79a9d36ddebee59660bd2abbf738f940f5b` |
| `Muse-Glimmer-30B-UD-Q6_K_XL.gguf` | unsloth @ faa5b025c584 | 26,265,362,976 | `fb5f80d110c4fa932cc652e70873c0bd12c0954009038aa675e65086104c2739` |
| `Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf` | meta-models @ 70bf1b61ac09 | 19,653,960,832 | `ac7023d6a4c704eb9af54ab53e476a66b7f5b6c0ef2fc4a8dde5253c291a6c38` |

¹ The Q8_0 file existed before the study and was not re-hashed during it. Its size matches. The hash prefix and
suffix recorded with the profile (`f2c087d6…0b86`) match the Hugging Face LFS hash above. Its original download
revision was not recorded. The other four files were hashed locally and match the hashes shown
(`results/environment/model_hashes.txt`).

GGUF headers (`results/environment/gguf_headers.txt`) show that the Q8, Q5 and Q6 files store the sliding-window
pattern as the scalar 4, while Meta's Dynamic Q4 stores it as a 52-entry bool array. Dynamic + DFlash was not run.

## Results

Every number below can be recomputed from `results/` with `python3 tools/claims.py`; `tests/test_claims.py`
pins the headline ones. The numbers match the study's own report.

### Decode speed: full matrix, tok/s, median (min–max), n = 5 (`results/speed_matrix.csv`)

| config | review512 | reason512 | review 8K | review 16K | review 32K | review 64K | warm 16K | legacy256 |
|---|---|---|---|---|---|---|---|---|
| A1 control | 7.61 | 7.62 | 7.56 | 7.53 | 7.47 | 7.37 (7.3–7.4) | 7.53 | 7.62 |
| Q8 + DF7 | **27.71** (19.0–28.2) | **15.92** (12.6–21.9) | 18.41 (15.6–19.6) | 17.99 (13.1–21.3) | 18.36 (15.0–18.6) | 15.88 (14.9–22.7) | 17.04 | 15.04 |
| Q5 | 11.67 | 11.68 | 11.54 | 11.48 | 11.36 | 11.12 | 11.48 | 11.69 |
| Q5 + DF7 | **29.86** (27.3–43.2) | **20.71** (15.9–25.9) | 21.81 (18.9–35.3) | 20.83 (19.0–25.7) | 20.49 (18.9–26.1) | 20.66 (19.4–23.8) | 21.66 | 17.82 |

Speed-up of the median over A1:

| config | range over the 8 workloads | without legacy256 | reasoning | review 32K |
|---|---|---|---|---|
| Q8 + DF7 | 1.97–3.64× | 2.09–3.64× | 2.09× | 2.46× |
| Q5 | 1.51–1.53× | 1.51–1.53× | 1.53× | 1.52× |
| Q5 + DF7 | 2.34–3.92× | 2.72–3.92× | 2.72× | 2.74× |

The study's summary reads "2.1–3.6×, median 15.0–27.7 tok/s" for Q8 + DF7. The 15.0 tok/s end of that tok/s range is
the legacy256 fixture, which is 1.97×, so the ratio range quoted beside it leaves that fixture out.

**Other speed results:**

- **Prefill** (cold-cache median tok/s / TTFT s, `results/speed_matrix.csv`):

  | config | 512 | 8K | 16K | 32K | 64K | warm 16K TTFT |
  |---|---|---|---|---|---|---|
  | A1 | 245 / 2.5 | 297 / 26.6 | 291 / 53.3 | 278 / 108.9 | 255 / 235.9 | 1.0 s |
  | Q8 + DF7 | 235 / 2.3 | 289 / 27.5 | 285 / 54.2 | 272 / 114.4 | 250 / 243.8 | 0.8 s |
  | Q5 | 247 / 2.3 | 304 / 25.7 | 303 / 51.2 | 290 / 104.4 | 265 / 226.4 | 1.5 s |
  | Q5 + DF7 | 236 / 2.2 | 298 / 26.2 | 296 / 52.2 | 284 / 106.4 | 260 / 231.1 | 1.5 s |

  DFlash costs about 2–3% of prefill throughput.
- **Draft acceptance** (accepted/drafted over 5 reps):

  | config | review512 | reason512 | 8K | 16K | 32K | 64K |
  |---|---|---|---|---|---|---|
  | Q8 + DF7 | 44% (3853/8769) | 23% (3124/13871) | 28% | 28% | 29% | 30% |
  | Q5 + DF7 | 44% (3863/8711) | 23% (3166/13570) | 31% | 28% | 29% | 31% |

  DFlash drafts blocks of up to 7 tokens, so a low per-token acceptance still yields several accepted tokens per
  verification step.
- **Matrix health:** 0 errors in 180 records. No repetition collapse (max repeated-window score 0.037). Swap 0.0 GiB.
  40 of the 512-prompt records stopped at the 1,024-token cap by design, which makes them fixed-length decode
  measurements.
- **Screen** (median of 2, `results/screen.csv`; review512 / reason512 / review 32K):

  | config | review512 | reason512 | review 32K |
  |---|---|---|---|
  | A0 | 7.62 | 7.65 | 7.50 |
  | A1 | 7.65 | 7.62 | 7.51 |
  | ngram-simple (B) | 11.77 | 7.90 | 8.05 |
  | ngram-mod (C) | 11.95 | 7.80 | 7.75 |
  | DF3 | 20.12 | 16.23 | 16.67 |
  | DF7 | 27.35 | 17.51 | 17.30 |
  | DF15 | 13.00 | 7.98 | 9.37 |
  | Q4 Dynamic | 10.90 | 10.91 | 10.62 |
  | Q5 | 11.67 | 11.68 | 11.35 |
  | Q6 | 8.20 | 8.18 | 8.04 |
  | Q5 + DF7 (separate screen run) | 34.92 | 23.10 | 23.46 |

  ngram speculation helped only when the model quoted code verbatim. DF15 drafted too far ahead and wasted drafts.
  Q4 Dynamic and Q6 were dominated by Q5.
- **Memory** (peak GTT+VRAM / minimum MemAvailable, GiB, `results/memory_peaks.csv`):

  | config | peak GTT+VRAM | min MemAvailable |
  |---|---|---|
  | A1 | 31.6 | 76.1 |
  | Q8 + DF7 | 34.5 | 74.5 |
  | Q5 | 21.9 | 87.5 |
  | Q5 + DF7 | 24.4 | 82.6 |

### Correctness gates

- **Passkey** (`results/passkey.csv`): 30/30 for A1, Q8 + DF7, Q5 and Q5 + DF7.
- **Tool calls** (`results/toolsmoke.csv`):
  - 14/14 historical records and 18/18 added tool-call-first records for A0, A1, Q8 + DF7, Q5 and Q5 + DF7.
  - There were no markup leaks, malformed arguments or `finish=length`.
  - See the limitations for what the tool-call-first records did not show.
- **Template** (`results/tplcheck.csv`): 3/3 for every configuration. All five configurations rendered byte-identical
  output, shown once in `results/tplcheck_rendered.txt`.
- **Greedy comparison** (temp 0, top_k 1, seed 1, 3 prompts, `results/greedy.csv`). Speculative decoding is **not**
  byte-identical to the control:

  | comparison | prompt 0 | prompt 1 | prompt 2 |
  |---|---|---|---|
  | A1 run 2 vs A1 run 1 | identical (2496/2496) | identical (1239/1239) | diverges at 619 / 1007 |
  | Q8 + DF3 vs A1 | diverges at 1150 / 2496 | diverges at 449 / 1239 | diverges at 619 / 1007 |
  | Q8 + DF7 vs A1 | diverges at 2137 / 2496 | diverges at 544 / 1239 | diverges at 634 / 1007 |

  ("diverges at N / M" = N common prefix characters out of M in A1 run 1.) The control is not deterministic either
  on prompt 2. The diverged texts were not judged, so quality equivalence rests on the task gates and the blind
  grade.

### Review/explore: harness auto-scorer (`results/quality_runs.csv`)

| config | run | standard planted bugs | std auto-FP | hard planted bugs | hard auto-FP | answers | finish≠stop | median wall s review / explore |
|---|---|---|---|---|---|---|---|---|
| baseline Q8 (2026-09-28) | 1 | 6/6 | 0 | 4/4 | 1 | 11 | 0 | 359 / 589 |
| Q8 + DF7 | 1 | 6/6 | 0 | 4/4 | 0 | 11 | 0 | 162 / 226 |
| Q8 + DF7 | 2 | 6/6 | 0 | 4/4 | 0 | 11 | 0 | 176 / 243 |
| Q5 | 1 | 6/6 | 1 | 4/4 | 0 | 11 | 0 | 287 / 426 |
| Q5 | 2 | 6/6 | 0 | 4/4 | 1 | 11 | 0 | 273 / 401 |
| Q5 + DF7 | 1 | 6/6 | 1 | 4/4 | 0 | 11 | 0 | 145 / 184 |
| Q5 + DF7 | 2 | 6/6 | 0 | 4/4 | 2 | 11 | 0 | 156 / 197 |

"Auto-FP" is the regex matcher's unadjudicated false-positive count. The blind grade is the authority on false
alarms.

### Blind grade (`results/blind/grades_by_config.json`)

| source | answers | mean of C, G, U (quoted) | mean of all 5 axes | planted bugs found | false alarms | wrong citations |
|---|---:|---:|---:|---|---:|---:|
| baseline Q8 | 11 | **3.82** | 3.93 | 10/10 | 2 | 3 |
| Q8 + DF7 | 22 | **3.79** | 3.89 | 20/20 | 1 | 8 |
| Q5 + DF7 | 22 | **3.74** | 3.85 | 20/20 | 3 | 3 |

C = correctness, G = groundedness, U = usefulness. No hallucinated citations were found in any answer. The
orchestrator judged the result a tie within noise and promoted Q8 + DF7. Q5 + DF7 was not adopted. Q5 alone was not
graded.

### Hard agentic tasks at the 900 s cap (`results/agentic_runs.csv`)

| config | task | run | end | steps | wall s | hidden tests |
|---|---|---|---|---:|---:|---|
| baseline Q8 | h1_refunds | 1, 2 | api_timeout | 2, 2 | 930.1, 930.1 | 7/29, 7/29 |
| baseline Q8 | h2_schedule_tz | 1, 2 | api_timeout | 4, 4 | 930.1, 930.1 | 5/25, 5/25 |
| Q8 + DF7 | h1_refunds | 1 | api_timeout | 11 | 930.1 | **29/29** |
| Q8 + DF7 | h1_refunds | 2 | model_finished | 9 | 917.6 | **29/29** |
| Q8 + DF7 | h2_schedule_tz | 1, 2 | api_timeout | 17, 5 | 930.1, 930.1 | 5/25, 5/25 |
| Q5 + DF7 | h1_refunds | 1 | api_timeout | 11 | 934.0 | **29/29** |
| Q5 + DF7 | h1_refunds | 2 | model_finished | 7 | 798.4 | **29/29** |
| Q5 + DF7 | h2_schedule_tz | 1, 2 | api_timeout | 5, 6 | 930.1, 930.1 | 5/25, 5/25 |

- **Solved per wall-clock hour:** baseline 0, Q8 + DF7 1.94, Q5 + DF7 2.0.
- **What `api_timeout` means:** the harness's read timeout at the wall cap, not a server error.
- **Run 1 of h1:** the hidden tests already passed when the cap cut off the model's closing turn.
- **h2:** stayed out of reach for every configuration.

### Deployment check (2026-09-29, `results/deployment_check_*.csv`)

After grading, Q8 + DF7 was added as a new profile on the production llama-swap; the old profile was kept for
rollback. A check on the deployed profile gave the following:

- **Speed:** three ~450-token code-review prompts at high reasoning decoded at 30.00 / 22.97 / 26.88 tok/s
  (median 26.88).
- **Draft acceptance:** 56% / 39% / 48%.
- **Prefill:** 218.7–238.9 tok/s.
- **Tools:** toolsmoke 32/32.

## Limitations

These are listed so the result is not over-read. Items marked **inconclusive** are open questions, not findings.

1. **The quality evidence is thin.**
   - One grader, one packet, 11 tasks, and 11 or 22 answers per source. There is no second grader and no
     agreement measure.
   - The "tie" is the orchestrator's judgement. No statistical test was run.
   - The composite (mean of C, G, U) was not documented when it was used; it was reconstructed here.
   - Against the pre-set rule:
     - Q5 + DF7 had more false alarms than the baseline in total (3 against 2, from twice as many answers).
     - Q8 + DF7 had more wrong citations: 8 over 4 cited-explore answers (2.0 per answer), against 3 over 2 (1.5 per
       answer).
     - Whether these are noise is **inconclusive** at this sample size.
   - The same baseline answers scored higher in an earlier, separately graded packet from the parent eval (that packet
     and its grades are not part of this bundle). Absolute scores therefore depend on the grader and the packet;
     only comparisons within one packet are meaningful.
2. **The baseline is confounded with build and date.** Baseline answers came from the 7d6f5d02b build on the
   previous day; candidates ran on 7ab4ee7ba. A0 and A1 matched on speed, template output and tool calls, but
   answer quality was not compared directly between the two builds.
3. **The tool-call-first check is inconclusive.**
   - The 18 added tool-call-first records were meant to exercise the llama.cpp PR #29242 path: a call emitted with
     no reasoning first. In every configuration, all 18 had reasoning before the call (`tool_call_first` is False
     in every row of `results/toolsmoke.csv`).
   - The study's report counted 3–4 "true no-reasoning first calls" per configuration. Those records are the
     history-continuation cases (`hist_json`, `hist_plain`), counted by `summarize.py`'s broader definition (any
     call with zero reasoning characters).
   - The response text was not kept, so whether those outputs took the PR #29242 path cannot be checked. The
     regression is not shown to be fixed; it was not reproduced on either build.
4. **Decoding is not byte-equivalent** (greedy comparison above). It is lossless in principle, but numerically
   different on this Vulkan backend.
5. **Agentic evidence is small:** 2 tasks × 2 runs.
   - h1's margin under the cap was 18 s for Q8 + DF7 and 102 s for Q5 + DF7, in the runs that finished cleanly.
   - The baseline's 7/29 (h1) and every 5/25 (h2) equal the score of the **unmodified** task repository. This was
     checked while preparing this bundle by running the harness against a stub server that makes no edits. Those
     runs made no net progress on the hidden tests.
6. **The host rebooted mid-study.**
   - At 16:45 on 2026-09-28 the host rebooted into a staged OS update (kernel 7.2.4 → 7.2.7). The study did not
     cause this.
   - The screen ran before the reboot; the full matrix, the agentic runs and most gates ran after it. Each stage
     compares configurations within one boot.
   - Three in-flight 116K DF7 passkey records were lost to connection-refused and re-run
     (`results/passkey_reboot_interrupted.csv`).
   - A post-reboot check (`results/postreboot_check.csv`) reproduced the pre-reboot speeds.
7. **One machine, one backend.** Strix Halo, Vulkan/RADV, a single host. The results may not transfer to ROCm, CUDA,
   Metal or other memory systems.
8. **The passkey haystack depends on the Python version.** It is built from the local Python stdlib
   (`GS_STDLIB_GLOB`), so a different Python version gives a different haystack. The "116000" target reached about
   106–107K prompt tokens.
9. **Q5 changes the weights.** Unlike DFlash, which leaves the Q8 target in charge of every token, Q5 is a
   different, smaller quantisation of the model. Its publisher reports a small divergence from BF16; that figure was
   not verified here.
10. **The memory log is coarse:** samples are one per minute, and only from samples where a single candidate was
    loaded.

## Reproduction

You need: a Linux machine with a GPU llama.cpp supports, about 100 GB of disk for all five GGUF files, two llama.cpp
builds (7d6f5d02b and 7ab4ee7ba, or newer builds; record which), [llama-swap](https://github.com/mostlygeek/llama-swap),
the `hf` CLI, and Python 3 with `requests` and `pytest` (`pip install -r requirements.txt`).

1. **Get the models:**
   `GS_MODEL_DIR=/path/to/models scripts/download.sh`. The script pins the revisions above. Check the hashes against
   `results/environment/model_hashes.txt`.
2. **Build llama.cpp:**
   ```sh
   git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
   git checkout 7ab4ee7ba
   cmake -B build -DGGML_VULKAN=ON -DGGML_NATIVE=ON -DCMAKE_BUILD_TYPE=Release
   cmake --build build -j
   ```
   Repeat at `7d6f5d02b` for A0 and the baseline, or skip them.
3. **Configure the server:** edit the `/path/to/...` values in `config/llama-swap.test.yaml`, then run
   `llama-swap -config config/llama-swap.test.yaml -listen 127.0.0.1:8080`.
4. **Point the scripts at it:** see [Configuration](#configuration). For example:
   `export GS_BASE=http://localhost:8080`.
5. **Run the study:**
   ```sh
   cp config/queue.study.txt queue.txt
   mkdir -p runs logs
   scripts/queue_runner.sh
   ```
   Optionally run `scripts/memlog.sh > runs/mem_log.txt &` alongside. The queue runs one job at a time, so no two
   models generate at once. In the study the combo stage was gated by hand: `touch GO_COMBO` once DF7 and Q5 have
   each passed. Expect roughly a day of machine time on hardware like the study's.
6. **Summarise:**
   ```sh
   python3 tools/export_summaries.py --study runs --baseline-std runs/baseline_std.jsonl --baseline-hard runs/baseline_hard.jsonl --out my-results
   python3 tools/claims.py my-results
   ```
   `scripts/tables.py` and `scripts/summarize.py` print the study's own tables from `runs/`.
7. **Blind grade:**
   - Run `python3 scripts/build_blind_gs.py g-df7 g-combo1`, which writes `runs/grading-packet/packet.md` and
     `runs/KEY.json`.
   - Give the grader only `packet.md`, and ask for `GRADES.json` in the layout of `results/blind/GRADES.json`.
   - Then run `python3 tools/blind_summary.py GRADES.json runs/KEY.json`.

To check this repo without a GPU: `python3 -m pytest -q tests` (it needs `requests` and `pytest`).

### Configuration

| variable | default | used by |
|---|---|---|
| `GS_BASE` | `http://localhost:8080` | test llama-swap: bench, passkey, greedy, toolsmoke, tplcheck, harness `g-*` |
| `GS_BASELINE_BASE` | `$GS_BASE` | harness profile `muse-glimmer-30b` (baseline) |
| `GS_PROD_BASE` | empty (check off) | optional second server whose `/running` list is logged with each record |
| `GS_RESULTS_DIR` | `runs/` | raw outputs for the harness, `tables.py` and `build_blind_gs.py` |
| `GS_BASELINE_STD`, `GS_BASELINE_HARD` | `runs/baseline_{std,hard}.jsonl` | baseline answers for `tables.py` and `build_blind_gs.py` |
| `GS_EVAL_ROOT` | repo root | where `tasks/` and `tasks_hard/` live |
| `GS_PYTHON` | current interpreter | Python with pytest, for the agentic tasks' tests |
| `EVAL_WORK` | `$TMPDIR/model-eval-work` | scratch copies of agentic task repos |
| `EVAL_WALL_CAP` | 900 | agentic wall cap in seconds (the study used 900) |
| `GS_STDLIB_GLOB` | this Python's stdlib | passkey/bench haystack source; the study used a system Python 3.1x stdlib |
| `GS_FIRST_TRIES` | 3 | tool-call-first repetitions |
| `GS_MODEL_DIR` | `./models` | `download.sh` |
| `GS_DRM_DEVICE` | `/sys/class/drm/card1/device` | `memlog.sh` (amdgpu sysfs) |
| `GS_WORKDIR` | repo root | `queue_runner.sh`, `run_controls.sh` |

## Scripts

These are ports of the study's scripts. Only portability and scrubbing changed: hard-coded paths, hosts and ports
became the variables above; non-study model entries were removed from the harness; raw outputs moved from `results/`
to `runs/`. Comments in the code mark the two additions:

- the baseline profile in the llama-swap config;
- the Q8 line in `download.sh`.

`scripts/blind_text.py` holds the rubric text and name scrubber, copied verbatim from the parent eval that
`build_blind_gs.py` imported them from.

| script | role |
|---|---|
| `harness_gs.py` | agentic/review/explore harness (OpenAI-compatible `/v1/chat/completions`) |
| `bench_gs.py`, `gslib.py` | speed screen and matrix; shared helpers |
| `passkey_gs.py`, `toolsmoke_gs.py`, `tplcheck_gs.py`, `greedy_gs.py` | correctness gates and the greedy diagnostic |
| `summarize.py`, `tables.py` | the study's own table printers (read raw `runs/`) |
| `build_blind_gs.py`, `blind_text.py` | blind packet builder |
| `gguf_meta.py` | minimal GGUF metadata reader |
| `queue_runner.sh`, `run_controls.sh`, `memlog.sh`, `download.sh` | job queue, A0/A1 controls, memory logger, model download |

`results/tables.md` is the study's own `tables.py` output from the raw files. The ported `tables.py` reproduces it
byte for byte from the same inputs.

## Dates

| date | event |
|---|---|
| 2026-09-28 | Baseline Q8 review/explore/agentic answers (the eval before this study) |
| 2026-09-28 13:48 – 2026-09-29 10:22 | Study runs (screen, gates, matrix, quality, agentic) |
| 2026-09-28 16:45 | Unplanned host reboot (kernel update) |
| 2026-09-29 ~10:27–10:32 | Blind grading |
| 2026-09-29 10:34 | Q8 + DF7 added to the production llama-swap |
| 2026-10-07 | This bundle prepared; model licence tags checked on Hugging Face |

## Third-party material

| material | licence | in this repo? |
|---|---|---|
| Muse Glimmer 30B GGUFs (Meta; Unsloth quantisations) | Apache-2.0 per the Hugging Face repo tags | No: hashes and links only |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | No: commits named |
| [llama-swap](https://github.com/mostlygeek/llama-swap) | MIT | No: config only |
| Python standard library source (passkey/bench haystack) | PSF License | No: read at run time from the local install |
| `requests`, `pytest` | Apache-2.0, MIT | No: `requirements.txt` |

The task inputs (`tasks/`, `tasks_hard/`) are synthetic code, logs and docs written for the parent eval. The answers
in `results/blind/packet.md` were generated by the evaluated models. The grades in `results/blind/GRADES.*` were
written by the grader.

No licence has been chosen for this repository yet.
