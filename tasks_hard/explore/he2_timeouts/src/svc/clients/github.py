import requests

API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str, settings):
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.settings = settings

    def get_repo(self, name: str) -> dict:
        r = self.session.get(f"{API}/repos/{name}", timeout=10)
        r.raise_for_status()
        return r.json()

    def list_issues(self, name: str) -> list:
        r = self.session.get(f"{API}/repos/{name}/issues",
                             timeout=(self.settings.connect_timeout, self.settings.read_timeout))
        r.raise_for_status()
        return r.json()

    def download_archive(self, name: str, dest) -> None:
        with self.session.get(f"{API}/repos/{name}/tarball", stream=True) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1 << 16):
                dest.write(chunk)
