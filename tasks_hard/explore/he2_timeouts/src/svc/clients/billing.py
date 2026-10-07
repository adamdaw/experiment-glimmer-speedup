import json
import urllib.request

import httpx

BILLING = "https://billing.internal"


class BillingClient:
    def __init__(self, timeout: float | None = None):
        self.timeout = timeout
        self.http = httpx.Client(base_url=BILLING)

    def invoice(self, invoice_id: str) -> dict:
        return self.http.get(f"/invoices/{invoice_id}").json()

    def charge(self, payload: dict) -> dict:
        return self.http.post("/charges", json=payload, timeout=None).json()

    def legacy_balance(self, account: str) -> dict:
        req = urllib.request.Request(f"{BILLING}/v0/balance?account={account}")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)

    def health(self) -> bool:
        with urllib.request.urlopen(f"{BILLING}/health", timeout=2) as resp:
            return resp.status == 200
