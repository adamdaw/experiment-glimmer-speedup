import json
from pathlib import Path

from .model import Job
from .parse import parse


def save(path: Path, jobs: list[Job]) -> None:
    data = {"version": 1, "jobs": [{"name": j.name, "spec": j.spec} for j in jobs]}
    Path(path).write_text(json.dumps(data, indent=2))


def load(path: Path) -> list[Job]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [Job(j["name"], j["spec"], parse(j["spec"])) for j in data["jobs"]]
