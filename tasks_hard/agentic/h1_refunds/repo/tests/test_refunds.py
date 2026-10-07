from decimal import Decimal

import pytest

from billing.errors import OverRefund
from billing.invoice import Invoice, Line
from billing.money import Money, allocate
from billing.refunds import RefundService
from billing.store import InMemoryStore


class FakeGateway:
    def __init__(self):
        self.calls = []

    def refund(self, payment_id, cents, key):
        self.calls.append((payment_id, cents, key))


def make(lines=None):
    store = InMemoryStore()
    inv = Invoice("inv1", "EUR", lines or [Line("a", 1000, Decimal("0.2")), Line("b", 500, Decimal("0.2")),
                                            Line("c", 333, Decimal("0"))], payment_id="pay1")
    store.add_invoice(inv)
    gw = FakeGateway()
    return RefundService(store, gw), store, gw, inv


def test_allocate_sums_exactly():
    parts = allocate(100, [1, 1, 1])
    assert sum(parts) == 100
    assert parts == [34, 33, 33]


def test_partial_refund_parts_sum_to_amount():
    svc, store, gw, inv = make()
    r = svc.refund("inv1", Money(1014, "EUR"), "k1")
    assert sum(r.line_parts) == 1014
    assert gw.calls == [("pay1", 1014, "k1")]


def test_cannot_refund_more_than_total_across_refunds():
    svc, store, gw, inv = make()
    assert inv.total_cents == 2133
    svc.refund("inv1", Money(2000, "EUR"), "k1")
    with pytest.raises(OverRefund):
        svc.refund("inv1", Money(200, "EUR"), "k2")


def test_replay_same_key_returns_same_refund():
    svc, store, gw, inv = make()
    r1 = svc.refund("inv1", Money(500, "EUR"), "k1")
    r2 = svc.refund("inv1", Money(500, "EUR"), "k1")
    assert r2.refund_id == r1.refund_id
    assert len(gw.calls) == 1
