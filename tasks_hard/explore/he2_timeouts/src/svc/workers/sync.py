from ..clients.billing import BillingClient
from ..clients.github import GitHubClient
from ..config import load
from .fetch import fetch_all


def nightly(token: str, repos: list[str], mirrors: list[str]) -> None:
    settings = load()
    gh = GitHubClient(token, settings)
    billing = BillingClient(timeout=settings.read_timeout)
    for name in repos:
        gh.get_repo(name)
        gh.list_issues(name)
    billing.legacy_balance("ops")
    fetch_all(mirrors, timeout=(settings.connect_timeout, 30))
    fetch_all(["https://status.internal/ping"])
