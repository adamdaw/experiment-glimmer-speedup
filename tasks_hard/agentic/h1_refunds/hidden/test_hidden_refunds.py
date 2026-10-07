from decimal import Decimal

import pytest

from billing.errors import CurrencyMismatch, IdempotencyConflict, NotPaid, OverRefund
from billing.invoice import Invoice, Line
from billing.money import Money, allocate
from billing.refunds import RefundService
from billing.store import InMemoryStore


class FakeGateway:
    def __init__(self, fail_times=0):
        self.calls = []
        self.fail_times = fail_times

    def refund(self, payment_id, cents, key):
        self.calls.append((payment_id, cents, key))
        if self.fail_times:
            self.fail_times -= 1
            raise TimeoutError("gateway timeout")


def make(gw=None, paid=True):
    store = InMemoryStore()
    inv = Invoice("inv1", "EUR", [Line("a", 1000, Decimal("0.2")), Line("b", 500, Decimal("0.2")),
                                  Line("c", 333, Decimal("0"))], payment_id="pay1" if paid else None)
    store.add_invoice(inv)
    gw = gw or FakeGateway()
    return RefundService(store, gw), store, gw, inv


# ---- allocate
@pytest.mark.parametrize("total,weights,expected", [
    (100, [1, 1, 1], [34, 33, 33]),
    (10, [3, 3, 3, 1], [3, 3, 3, 1]),
    (7, [1, 0, 1], [4, 0, 3]),
    (5, [2, 2, 1], [2, 2, 1]),
    (1, [1, 1], [1, 0]),
    (0, [5, 5], [0, 0]),
    (1014, [1200, 600, 333], [571, 285, 158]),
    (2, [1, 3, 3], [0, 1, 1]),
])
def test_allocate_largest_remainder(total, weights, expected):
    assert allocate(total, weights) == expected


def test_allocate_zero_weight_gets_zero():
    assert allocate(999, [0, 7, 0, 2]) [0] == 0
    parts = allocate(999, [0, 7, 0, 2])
    assert parts[2] == 0 and sum(parts) == 999


@pytest.mark.parametrize("total,weights", [(-1, [1]), (5, [0, 0]), (5, [2, -1]), (5, [])])
def test_allocate_rejects_bad_input(total, weights):
    with pytest.raises(ValueError):
        allocate(total, weights)


def test_allocate_sum_invariant_many():
    for total in range(0, 300, 7):
        for weights in ([1, 2, 3], [5, 5, 5, 5, 1], [1000, 1], [3, 0, 3]):
            assert sum(allocate(total, weights)) == total


# ---- refund validation
def test_not_paid():
    svc, store, gw, inv = make(paid=False)
    with pytest.raises(NotPaid):
        svc.refund("inv1", Money(10, "EUR"), "k")
    assert gw.calls == [] and store.refunds == {}


def test_currency_mismatch_no_side_effects():
    svc, store, gw, inv = make()
    with pytest.raises(CurrencyMismatch):
        svc.refund("inv1", Money(10, "USD"), "k")
    assert gw.calls == [] and store.refunds == {}


@pytest.mark.parametrize("cents", [0, -5])
def test_non_positive_amount(cents):
    svc, store, gw, inv = make()
    with pytest.raises(ValueError):
        svc.refund("inv1", Money(cents, "EUR"), "k")
    assert gw.calls == [] and store.refunds == {}


def test_over_refund_single_no_gateway_call():
    svc, store, gw, inv = make()
    with pytest.raises(OverRefund):
        svc.refund("inv1", Money(2134, "EUR"), "k")
    assert gw.calls == [] and store.refunds == {}
    assert inv.refunded_cents == 0


def test_exact_full_refund_then_nothing_more():
    svc, store, gw, inv = make()
    r = svc.refund("inv1", Money(2133, "EUR"), "k1")
    assert r.line_parts == (1200, 600, 333)
    with pytest.raises(OverRefund):
        svc.refund("inv1", Money(1, "EUR"), "k2")
    assert len(gw.calls) == 1


def test_over_refund_after_partial_records_nothing():
    svc, store, gw, inv = make()
    svc.refund("inv1", Money(2000, "EUR"), "k1")
    with pytest.raises(OverRefund):
        svc.refund("inv1", Money(134, "EUR"), "k2")
    assert len(store.refunds) == 1 and len(gw.calls) == 1
    svc.refund("inv1", Money(133, "EUR"), "k3")
    assert inv.refunded_cents == 2133


def test_refunded_cents_tracks_total():
    svc, store, gw, inv = make()
    svc.refund("inv1", Money(100, "EUR"), "k1")
    svc.refund("inv1", Money(250, "EUR"), "k2")
    svc.refund("inv1", Money(250, "EUR"), "k2")  # replay: no change
    assert inv.refunded_cents == 350


# ---- allocation by remaining refundable amount
def test_second_refund_weights_by_remaining():
    svc, store, gw, inv = make()
    r1 = svc.refund("inv1", Money(1014, "EUR"), "k1")
    assert r1.line_parts == (571, 285, 158)
    r2 = svc.refund("inv1", Money(1000, "EUR"), "k2")
    # remaining per line: 629, 315, 175 (sum 1119)
    assert r2.line_parts == tuple(allocate(1000, [629, 315, 175]))
    assert r2.line_parts == (562, 282, 156)


def test_parts_never_exceed_line_remaining():
    svc, store, gw, inv = make()
    total_parts = [0, 0, 0]
    for i, cents in enumerate([700, 700, 700, 33]):
        r = svc.refund("inv1", Money(cents, "EUR"), f"k{i}")
        total_parts = [a + b for a, b in zip(total_parts, r.line_parts)]
    assert total_parts == [1200, 600, 333]


# ---- idempotency
def test_replay_does_not_call_gateway_or_record_again():
    svc, store, gw, inv = make()
    r1 = svc.refund("inv1", Money(500, "EUR"), "k1")
    r2 = svc.refund("inv1", Money(500, "EUR"), "k1")
    assert r2 == r1
    assert len(store.refunds) == 1 and len(gw.calls) == 1


def test_replay_after_invoice_fully_refunded_still_returns_original():
    svc, store, gw, inv = make()
    r1 = svc.refund("inv1", Money(2133, "EUR"), "k1")
    assert svc.refund("inv1", Money(2133, "EUR"), "k1") == r1


def test_key_reuse_with_different_amount_conflicts():
    svc, store, gw, inv = make()
    svc.refund("inv1", Money(500, "EUR"), "k1")
    with pytest.raises(IdempotencyConflict):
        svc.refund("inv1", Money(501, "EUR"), "k1")
    assert len(store.refunds) == 1 and len(gw.calls) == 1


def test_key_reuse_with_different_invoice_conflicts():
    svc, store, gw, inv = make()
    store.add_invoice(Invoice("inv2", "EUR", [Line("x", 100)], payment_id="pay2"))
    svc.refund("inv1", Money(50, "EUR"), "k1")
    with pytest.raises(IdempotencyConflict):
        svc.refund("inv2", Money(50, "EUR"), "k1")


def test_gateway_failure_records_nothing_and_retry_with_same_key_works():
    gw = FakeGateway(fail_times=1)
    svc, store, gw, inv = make(gw)
    with pytest.raises(TimeoutError):
        svc.refund("inv1", Money(300, "EUR"), "k1")
    assert store.refunds == {} and inv.refunded_cents == 0
    r = svc.refund("inv1", Money(300, "EUR"), "k1")
    assert sum(r.line_parts) == 300
    assert gw.calls == [("pay1", 300, "k1"), ("pay1", 300, "k1")]
    assert inv.refunded_cents == 300
