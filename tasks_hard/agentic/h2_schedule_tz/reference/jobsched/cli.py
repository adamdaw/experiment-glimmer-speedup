"""Command line interface.

    python -m jobsched.cli --db jobs.json add NAME SPEC...
    python -m jobsched.cli --db jobs.json next NAME --now 2026-03-07T12:00:00+00:00

`add` stores a job (replacing any job with the same name) and prints "added NAME".
`next` prints the job's next run time strictly after --now as ISO 8601 in UTC,
e.g. "2026-03-08T14:30:00+00:00". Errors print "error: <message>" to stderr and
return exit code 2.
"""
import argparse
import sys
from datetime import datetime

from . import store
from .model import Job
from .next_run import next_run
from .parse import parse


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jobsched")
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("name")
    a.add_argument("spec", nargs="+")
    a.add_argument("--tz")
    n = sub.add_parser("next")
    n.add_argument("name")
    n.add_argument("--now", required=True)
    args = ap.parse_args(argv)
    try:
        jobs = store.load(args.db)
        if args.cmd == "add":
            spec = " ".join(args.spec)
            if args.tz:
                if "tz=" in spec.lower():
                    raise ValueError("use either --tz or tz=, not both")
                spec += f" tz={args.tz}"
            jobs = [j for j in jobs if j.name != args.name] + [Job(args.name, spec, parse(spec))]
            store.save(args.db, jobs)
            print(f"added {args.name}")
            return 0
        job = next((j for j in jobs if j.name == args.name), None)
        if job is None:
            raise ValueError(f"no job named {args.name!r}")
        now = datetime.fromisoformat(args.now)
        if now.tzinfo is None:
            raise ValueError("--now needs a UTC offset")
        print(next_run(job.schedule, now).isoformat())
        return 0
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
