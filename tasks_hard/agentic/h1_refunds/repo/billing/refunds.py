import itertools
from dataclasses import dataclass

from .errors import CurrencyMismatch, IdempotencyConflict, NotPaid, OverRefund  # noqa: F401
from .money import Money, allocate
from .store import InMemoryStore

_ids = itertools.count(1)


@dataclass(frozen=True)
class Refund:
    refund_id: str
    invoice_id: str
    amount: Money
    idempotency_key: str
    line_parts: tuple[int, ...]  # cents refunded per invoice line, same order as invoice.lines


class RefundService:
    def __init__(self, store: InMemoryStore, gateway):
        self.store = store
        self.gateway = gateway  # gateway.refund(payment_id: str, cents: int, idempotency_key: str)

    def refund(self, invoice_id: str, amount: Money, idempotency_key: str) -> Refund:
        """Refund `amount` (tax-inclusive) of a paid invoice. This docstring is the specification.

        1. The invoice must be paid (payment_id set), else NotPaid.
        2. amount.currency must equal the invoice currency, else CurrencyMismatch.
        3. amount.cents must be > 0, else ValueError.
        4. The total refunded on an invoice, across all refunds, may never exceed
           invoice.total_cents. A refund that would exceed it raises OverRefund.
        5. The refund is split across the invoice lines with money.allocate, weighted by
           each line's *remaining refundable* gross amount (line gross minus what earlier
           refunds already took from that line). The parts sum exactly to amount.cents
           and are stored on the Refund as line_parts.
        6. Idempotency: calling refund again with an idempotency_key that was already
           used for the same invoice_id and amount returns the originally created Refund
           (same refund_id) and changes nothing. Reusing a key with a different
           invoice_id or amount raises IdempotencyConflict.
        7. The gateway is called exactly once per new refund, with the idempotency key,
           and only after all validation passed. If the gateway raises, the exception
           propagates and nothing is recorded, so the caller may retry with the same key.
        Any error leaves the store and the invoice unchanged.
        """
        invoice = self.store.get_invoice(invoice_id)
        if invoice.payment_id is None:
            raise NotPaid(invoice_id)
        if amount.currency != invoice.currency:
            raise CurrencyMismatch(f"{amount.currency} != {invoice.currency}")
        self.gateway.refund(invoice.payment_id, amount.cents, idempotency_key)
        parts = allocate(amount.cents, [line.gross_cents for line in invoice.lines])
        refund = Refund(f"rf_{next(_ids)}", invoice_id, amount, idempotency_key, tuple(parts))
        self.store.save_refund(refund)
        return refund
