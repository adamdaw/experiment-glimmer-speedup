import itertools
from dataclasses import dataclass

from .errors import CurrencyMismatch, IdempotencyConflict, NotPaid, OverRefund
from .money import Money, allocate
from .store import InMemoryStore

_ids = itertools.count(1)


@dataclass(frozen=True)
class Refund:
    refund_id: str
    invoice_id: str
    amount: Money
    idempotency_key: str
    line_parts: tuple[int, ...]


class RefundService:
    def __init__(self, store: InMemoryStore, gateway):
        self.store = store
        self.gateway = gateway

    def refund(self, invoice_id: str, amount: Money, idempotency_key: str) -> Refund:
        for r in self.store.refunds.values():
            if r.idempotency_key == idempotency_key:
                if r.invoice_id == invoice_id and r.amount == amount:
                    return r
                raise IdempotencyConflict(idempotency_key)
        invoice = self.store.get_invoice(invoice_id)
        if invoice.payment_id is None:
            raise NotPaid(invoice_id)
        if amount.currency != invoice.currency:
            raise CurrencyMismatch(f"{amount.currency} != {invoice.currency}")
        if amount.cents <= 0:
            raise ValueError("amount must be positive")
        prior = self.store.refunds_for(invoice_id)
        refunded = sum(r.amount.cents for r in prior)
        if refunded + amount.cents > invoice.total_cents:
            raise OverRefund(invoice_id)
        remaining = [line.gross_cents - sum(r.line_parts[i] for r in prior) for i, line in enumerate(invoice.lines)]
        parts = allocate(amount.cents, remaining)
        self.gateway.refund(invoice.payment_id, amount.cents, idempotency_key)
        refund = Refund(f"rf_{next(_ids)}", invoice_id, amount, idempotency_key, tuple(parts))
        self.store.save_refund(refund)
        invoice.refunded_cents = refunded + amount.cents
        return refund
