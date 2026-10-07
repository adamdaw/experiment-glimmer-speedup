"""Pins the numbers README.md quotes to the committed results/ files (via tools/claims.py)."""
from pathlib import Path

import pytest

import claims

R = Path(__file__).resolve().parent.parent / "results"


@pytest.fixture(scope="module")
def matrix():
    return claims.speed_matrix(R)


def med(matrix, cfg, wl):
    return round(matrix[(cfg, wl)]["tg_median"], 2)


def test_control_decode_medians(matrix):
    assert [med(matrix, "g-a1", w) for w in claims.WORKLOADS] == [7.61, 7.62, 7.56, 7.53, 7.47, 7.37, 7.53, 7.62]


def test_df7_decode_medians(matrix):
    assert [med(matrix, "g-df7", w) for w in claims.WORKLOADS] == [27.71, 15.92, 18.41, 17.99, 18.36, 15.88, 17.04, 15.04]


def test_combo_decode_medians(matrix):
    assert [med(matrix, "g-combo1", w) for w in claims.WORKLOADS] == [29.86, 20.71, 21.81, 20.83, 20.49, 20.66, 21.66, 17.82]


def test_speedup_ranges(matrix):
    def ratios(cfg, wls):
        return [matrix[(cfg, w)]["tg_median"] / matrix[("g-a1", w)]["tg_median"] for w in wls]
    allw, nolegacy = claims.WORKLOADS, claims.WORKLOADS[:-1]
    assert (round(min(ratios("g-df7", nolegacy)), 2), round(max(ratios("g-df7", nolegacy)), 2)) == (2.09, 3.64)
    assert round(min(ratios("g-df7", allw)), 2) == 1.97
    assert (round(min(ratios("g-combo1", allw)), 2), round(max(ratios("g-combo1", allw)), 2)) == (2.34, 3.92)
    assert (round(min(ratios("g-q5", allw)), 2), round(max(ratios("g-q5", allw)), 2)) == (1.51, 1.53)


def test_matrix_health():
    assert claims.matrix_health(R) == {"records": 180, "errors": 0, "concurrent": 0, "finish_length_512": 40,
                                       "max_rep_score": 0.037, "max_swap_gib": 0.0}


def test_screen_df7_and_combo():
    s = claims.screen(R)
    assert [round(s[("g-df7", w)], 2) for w in ("review512", "reason512", "review32k")] == [27.35, 17.51, 17.30]
    assert [round(s[("g-combo1", w)], 2) for w in ("review512", "reason512", "review32k")] == [34.92, 23.10, 23.46]


def test_passkey_all_pass():
    assert {c: v[:2] for c, v in claims.passkey(R).items()} == {c: (30, 30) for c in ("g-a1", "g-df7", "g-q5", "g-combo1")}


def test_tools_and_tool_call_first_finding():
    t = claims.tools(R)
    for cfg in ("g-a0", "g-a1", "g-df7", "g-q5", "g-combo1"):
        assert t[cfg]["historical"] == (14, 14) and t[cfg]["first"] == (18, 18) and t[cfg]["tplcheck"] == (3, 3)
        # none of the dedicated tool-call-first cases produced a call without reasoning
        assert t[cfg]["first_without_reasoning"] == 0
        assert t[cfg]["no_reasoning_call_cases"] == ["hist_json", "hist_plain"]


def test_quality_auto_scorer():
    q = claims.quality(R)
    assert len(q) == 7
    assert all(v["std_found"] == (6, 6) and v["hard_found"] == (4, 4) and v["not_stop"] == 0 for v in q.values())
    assert (q[("baseline-q8", 1)]["wall_review"], q[("baseline-q8", 1)]["wall_explore"]) == (359, 589)
    assert (q[("g-df7", 1)]["wall_review"], q[("g-df7", 1)]["wall_explore"]) == (162, 226)


def test_agentic_solved_per_hour():
    a = claims.agentic(R)
    assert (a["baseline-q8"]["solved"], a["g-df7"]["solved"], a["g-combo1"]["solved"]) == (0, 2, 2)
    assert (a["g-df7"]["solved_per_hour"], a["g-combo1"]["solved_per_hour"]) == (1.94, 2.0)


def test_blind_grades():
    g = claims.grades(R)
    assert [g[c]["cgu_mean"] for c in ("baseline-Q8 (2026-09-28 eval)", "g-df7", "g-combo1")] == [3.82, 3.79, 3.74]
    assert [g[c]["five_axis_mean"] for c in ("baseline-Q8 (2026-09-28 eval)", "g-df7", "g-combo1")] == [3.93, 3.89, 3.85]
    assert [g[c]["false_alarms"] for c in ("baseline-Q8 (2026-09-28 eval)", "g-df7", "g-combo1")] == [2, 1, 3]


def test_deployment_check():
    d = claims.deployment(R)
    assert d["tg"] == [30.0, 22.97, 26.88] and d["acc"] == [56, 39, 48] and d["tools"] == (32, 32)
