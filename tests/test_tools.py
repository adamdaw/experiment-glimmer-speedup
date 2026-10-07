import json

import blind_summary
import export_summaries as ex


def test_common_prefix_counts_matching_characters():
    assert ex.common_prefix("abcdef", "abcxef") == 3
    assert ex.common_prefix("abc", "abc") == 3
    assert ex.common_prefix("abc", "abcd") == 3


def test_tplcheck_lines_are_parsed(tmp_path):
    f = tmp_path / "tplcheck_g-x.txt"
    f.write_text("[case one] reasoning in prompt: True\n    rendered...\n[case, two] reasoning in prompt: False\n")
    assert ex.tplcheck_rows(f, "g-x") == [{"config": "g-x", "case": "case one", "reasoning_in_prompt": True},
                                         {"config": "g-x", "case": "case, two", "reasoning_in_prompt": False}]


def test_memory_peaks_use_single_ready_candidate_samples_only(tmp_path):
    f = tmp_path / "mem.txt"
    f.write_text(
        "t1 avail=80.0GiB swap_used=0.00GiB gtt=20.0GiB vram=5.0GiB prod=[] test=[g-a:ready]\n"
        "t2 avail=70.0GiB swap_used=0.10GiB gtt=30.0GiB vram=5.0GiB prod=[] test=[g-a:starting]\n"
        "t3 avail=75.0GiB swap_used=0.00GiB gtt=22.0GiB vram=5.0GiB prod=[other] test=[g-a:ready]\n")
    rows, totals = ex.memory_rows(f)
    assert rows == [{"config": "g-a", "samples": 2, "peak_gtt_plus_vram_gib": 27.0, "min_mem_available_gib": 75.0,
                     "max_swap_used_gib": 0.0}]
    assert totals == {"samples": 3, "samples_with_other_server_model_loaded": 1}


def test_no_reasoning_call_flag():
    recs = [{"model": "m", "case": "hist_plain", "stream": False, "ok": True, "calls": [["f", {}]], "reasoning_chars": 0},
            {"model": "m", "case": "first_low_0", "stream": False, "ok": True, "calls": [["f", {}]], "reasoning_chars": 9,
             "tool_call_first": False}]
    assert [r["no_reasoning_call"] for r in ex.tool_rows(recs)] == [True, False]


def test_blind_summary_deanonymises_per_task_labels():
    g = {"A": {"t1": dict(correctness=5, groundedness=5, usefulness=5, completeness=5, concision=5, false_alarms=0)},
         "B": {"t1": dict(correctness=1, groundedness=2, usefulness=3, completeness=4, concision=5, false_alarms=2)}}
    key = {"t1": {"A": "cfg-x run2", "B": "baseline (old eval)"}}
    out = blind_summary.summarise(json.loads(json.dumps(g)), key)
    assert out["cfg-x"]["cgu_mean"] == 5.0 and out["cfg-x"]["false_alarms"] == 0
    assert out["baseline (old eval)"]["cgu_mean"] == 2.0 and out["baseline (old eval)"]["five_axis_mean"] == 3.0
