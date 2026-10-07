"""The harness's regex review scorer against the shipped rubric (no server needed)."""
import json
from pathlib import Path

import harness_gs

ROOT = Path(__file__).resolve().parent.parent


def test_split_items_numbered_list():
    assert harness_gs.split_items("intro\n1. first\n   more\n2. second") == ["1. first\n   more", "2. second"]


def test_empty_answer_finds_nothing():
    rub = json.loads((ROOT / "tasks/review/rubric.json").read_text())
    name = sorted(rub)[0]
    sc = harness_gs.score_review(name, "No issues found.")
    assert sc["recall"] == 0 and sc["false_positives"] == 0 and sc["n_items"] == 0


def test_tasks_resolve_relative_to_repo():
    assert harness_gs.ROOT == ROOT and (harness_gs.TASKS / "review" / "rubric.json").exists()
    prompt = harness_gs.build_single_prompt("explore", "e3_varint")
    assert "```python" in prompt


def test_planted_bugs_and_false_positive_are_counted():
    answer = ("1. [severity: high] report.py:get_report - cache key omits user, so users see each other's reports - add user_id\n"
              "2. [severity: medium] report.py:top_n - sorted() is ascending, returns the smallest amounts - reverse=True\n"
              "3. [severity: low] report.py:fmt - date format is ugly - use ISO")
    sc = harness_gs.score_review("r1_report_cache", answer)
    assert sc["recall"] == 1.0
    assert sc["found"] == {"cache_key_missing_user": 0, "top_n_ascending": 1}
    assert sc["false_positives"] == 1 and sc["unmatched"][0]["severity"] == "low"
