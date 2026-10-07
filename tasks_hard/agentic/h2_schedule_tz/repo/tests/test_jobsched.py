from datetime import datetime, time, timezone

from jobsched import store
from jobsched.cli import main
from jobsched.model import Job
from jobsched.next_run import next_run
from jobsched.parse import parse

UTC = timezone.utc


def test_parse_existing_forms():
    assert parse("daily 09:30").at == time(9, 30)
    assert parse("weekly fri 17:00").weekday == 4
    assert parse("every 15m").minutes == 15


def test_parse_tz():
    s = parse("daily 09:30 tz=Europe/Oslo")
    assert s.tz == "Europe/Oslo" and s.at == time(9, 30)
    assert parse("daily 09:30").tz == "UTC"


def test_next_run_oslo_winter():
    s = parse("daily 09:30 tz=Europe/Oslo")  # CET = UTC+1 in January
    got = next_run(s, datetime(2026, 1, 10, 12, 0, tzinfo=UTC))
    assert got == datetime(2026, 1, 11, 8, 30, tzinfo=UTC)


def test_cli_tz_flag(tmp_path, capsys):
    db = str(tmp_path / "jobs.json")
    assert main(["--db", db, "add", "standup", "daily", "09:30", "--tz", "Europe/Oslo"]) == 0
    capsys.readouterr()
    assert main(["--db", db, "next", "standup", "--now", "2026-07-01T00:00:00+00:00"]) == 0
    assert capsys.readouterr().out.strip() == "2026-07-01T07:30:00+00:00"  # CEST = UTC+2


def test_legacy_file_loads(tmp_path):
    p = tmp_path / "old.json"
    p.write_text('{"version": 1, "jobs": [{"name": "backup", "spec": "daily 02:00"}]}')
    jobs = store.load(p)
    assert jobs[0].schedule.tz == "UTC"
    assert next_run(jobs[0].schedule, datetime(2026, 5, 1, 3, 0, tzinfo=UTC)) == datetime(2026, 5, 2, 2, 0, tzinfo=UTC)
