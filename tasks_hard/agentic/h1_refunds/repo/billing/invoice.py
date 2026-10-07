from dataclasses import dataclass, field
from decimal import Decimal

from .money import Money, tax_cents


@dataclass
class Line:
    sku: str
    net_cents: int
    tax_rate: Decimal = Decimal("0")

    @property
    def tax(self) -> int:
        return tax_cents(self.net_cents, self.tax_rate)

    @property
    def gross_cents(self) -> int:
        """Tax-inclusive amount charged for this line."""
        return self.net_cents + self.tax


@dataclass
class Invoice:
    invoice_id: str
    currency: str
    lines: list[Line]
    payment_id: str | None = None  # set once the invoice has been paid
    refunded_cents: int = 0  # total refunded so far, tax-inclusive

    @property
    def total_cents(self) -> int:
        return sum(line.gross_cents for line in self.lines)

    @property
    def total(self) -> Money:
        return Money(self.total_cents, self.currency)
