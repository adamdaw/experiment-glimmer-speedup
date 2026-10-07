import json
from datetime import datetime, time, timedelta, timezone

import pytest

from jobsched import store
from jobsched.cli import main
from jobsched.model import Job, Schedule
from jobsched.next_run import next_run
from jobsched.parse import parse

UTC = timezone.utc


def utc(*a):
    return datetime(*a, tzinfo=UTC)


# ---- parsing
def test_keywords_case_insensitive_zone_preserved():
    s = parse("WEEKLY Sun 02:30 tz=America/New_York")
    assert s.kind == "weekly" and s.weekday == 6 and s.tz == "America/New_York"


def test_interval_accepts_tz():
    assert parse("every 45m tz=Asia/Kathmandu").tz == "Asia/Kathmandu"


def test_unknown_zone_value_error_mentions_zone():
    with pytest.raises(ValueError) as ei:
        parse("daily 09:30 tz=Mars/Olympus_Mons")
    assert "Mars/Olympus_Mons" in str(ei.value)


@pytest.mark.parametrize("spec", ["daily tz=UTC 09:30", "daily 09:30 tz=UTC tz=UTC", "daily 09:30 tz=", "tz=UTC"])
def test_bad_tz_placement(spec):
    with pytest.raises(ValueError):
        parse(spec)


def test_schedule_default_tz_field():
    assert Schedule("daily", at=time(1, 0)).tz == "UTC"


# ---- next_run basics
def test_naive_after_rejected():
    with pytest.raises(ValueError):
        next_run(parse("daily 09:30 tz=Europe/Oslo"), datetime(2026, 1, 1, 12, 0))
    with pytest.raises(ValueError):
        next_run(parse("every 5m"), datetime(2026, 1, 1, 12, 0))


def test_result_is_utc_aware():
    got = next_run(parse("daily 09:30 tz=Europe/Oslo"), utc(2026, 1, 10, 12))
    assert got.tzinfo == timezone.utc


def test_strictly_after_boundary():
    s = parse("daily 09:30 tz=Europe/Oslo")
    assert next_run(s, utc(2026, 1, 11, 8, 30)) == utc(2026, 1, 12, 8, 30)
    assert next_run(s, utc(2026, 1, 11, 8, 29, 59)) == utc(2026, 1, 11, 8, 30)


def test_after_with_non_utc_offset():
    s = parse("daily 09:30 tz=Europe/Oslo")
    after = datetime(2026, 1, 11, 14, 0, tzinfo=timezone(timedelta(hours=5)))  # 09:00Z
    assert next_run(s, after) == utc(2026, 1, 12, 8, 30)


def test_local_date_differs_from_utc_date():
    s = parse("daily 23:30 tz=America/Los_Angeles")  # PST = UTC-8
    assert next_run(s, utc(2026, 1, 10, 6, 0)) == utc(2026, 1, 10, 7, 30)
    assert next_run(s, utc(2026, 1, 10, 8, 0)) == utc(2026, 1, 11, 7, 30)


# ---- DST
def test_dst_gap_shifts_forward():
    s = parse("daily 02:30 tz=America/New_York")
    assert next_run(s, utc(2026, 3, 7, 12)) == utc(2026, 3, 8, 7, 30)  # 03:30 EDT
    assert next_run(s, utc(2026, 3, 8, 8)) == utc(2026, 3, 9, 6, 30)  # 02:30 EDT


def test_dst_overlap_first_occurrence_once():
    s = parse("daily 01:30 tz=America/New_York")
    assert next_run(s, utc(2026, 11, 1, 0)) == utc(2026, 11, 1, 5, 30)  # 01:30 EDT
    # between the two 01:30s: the second one must NOT run
    assert next_run(s, utc(2026, 11, 1, 5, 45)) == utc(2026, 11, 2, 6, 30)


def test_weekly_uses_local_weekday():
    s = parse("weekly mon 00:30 tz=Asia/Tokyo")
    assert next_run(s, utc(2026, 9, 26, 0)) == utc(2026, 9, 27, 15, 30)


def test_weekly_across_eu_dst_start():
    s = parse("weekly sun 09:00 tz=Europe/Oslo")
    assert next_run(s, utc(2026, 3, 28, 12)) == utc(2026, 3, 29, 7, 0)
    assert next_run(s, utc(2026, 3, 21, 12)) == utc(2026, 3, 22, 8, 0)


# ---- intervals ignore zone
def test_interval_anchored_to_utc_epoch():
    assert next_run(parse("every 45m tz=Asia/Kathmandu"), utc(2026, 1, 1, 0, 0)) == utc(2026, 1, 1, 0, 45)
    assert next_run(parse("every 60m"), datetime(2026, 1, 1, 10, 30, tzinfo=timezone(timedelta(hours=2)))) == utc(2026, 1, 1, 9, 0)


# ---- storage
def test_roundtrip_keeps_zone(tmp_path):
    p = tmp_path / "jobs.json"
    s = parse("daily 02:30 tz=America/New_York")
    store.save(p, [Job("a", "daily 02:30 tz=America/New_York", s), Job("b", "every 5m", parse("every 5m"))])
    jobs = store.load(p)
    assert [j.schedule.tz for j in jobs] == ["America/New_York", "UTC"]
    assert next_run(jobs[0].schedule, utc(2026, 3, 7, 12)) == utc(2026, 3, 8, 7, 30)


def test_legacy_file_multiple_jobs(tmp_path):
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"version": 1, "jobs": [{"name": "a", "spec": "weekly fri 17:00"},
                                                     {"name": "b", "spec": "every 30m"}]}))
    jobs = store.load(p)
    assert [j.schedule.tz for j in jobs] == ["UTC", "UTC"]
    assert next_run(jobs[0].schedule, utc(2026, 9, 27, 0)) == utc(2026, 10, 2, 17, 0)


# ---- CLI
def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out.strip(), out.err.strip()


def test_cli_tz_in_spec_and_weekly_flag(tmp_path, capsys):
    db = str(tmp_path / "j.json")
    assert run(capsys, "--db", db, "add", "a", "daily", "02:30", "tz=America/New_York")[0] == 0
    assert run(capsys, "--db", db, "add", "b", "weekly", "mon", "00:30", "--tz", "Asia/Tokyo")[0] == 0
    assert run(capsys, "--db", db, "next", "a", "--now", "2026-03-07T12:00:00+00:00")[1] == "2026-03-08T07:30:00+00:00"
    assert run(capsys, "--db", db, "next", "b", "--now", "2026-09-26T09:00:00+09:00")[1] == "2026-09-27T15:30:00+00:00"


def test_cli_tz_survives_reload(tmp_path, capsys):
    db = str(tmp_path / "j.json")
    run(capsys, "--db", db, "add", "a", "daily", "09:30", "--tz", "Europe/Oslo")
    run(capsys, "--db", db, "add", "other", "every", "5m")
    assert [j.schedule.tz for j in store.load(db)] == ["Europe/Oslo", "UTC"]


def test_cli_both_tz_forms_is_error(tmp_path, capsys):
    db = str(tmp_path / "j.json")
    code, out, err = run(capsys, "--db", db, "add", "a", "daily", "09:30", "tz=UTC", "--tz", "Europe/Oslo")
    assert code == 2 and err.startswith("error:")
    assert store.load(db) == []


def test_cli_unknown_zone(tmp_path, capsys):
    db = str(tmp_path / "j.json")
    code, out, err = run(capsys, "--db", db, "add", "a", "daily", "09:30", "--tz", "Nowhere/Land")
    assert code == 2 and err.startswith("error:") and "Nowhere/Land" in err


def test_cli_naive_now_is_error(tmp_path, capsys):
    db = str(tmp_path / "j.json")
    run(capsys, "--db", db, "add", "a", "daily", "09:30", "--tz", "Europe/Oslo")
    code, out, err = run(capsys, "--db", db, "next", "a", "--now", "2026-01-01T12:00:00")
    assert code == 2 and err.startswith("error:")
