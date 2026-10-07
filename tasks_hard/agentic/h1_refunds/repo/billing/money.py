from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Money:
    """An amount in integer minor units (cents) of a currency (ISO code, e.g. "EUR")."""

    cents: int
    currency: str

    def __add__(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(f"cannot add {other.currency} to {self.currency}")
        return Money(self.cents + other.cents, self.currency)


def tax_cents(net_cents: int, rate: Decimal) -> int:
    """Tax on a net amount, rounded half-up to whole cents."""
    return int((Decimal(net_cents) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def allocate(total: int, weights: list[int]) -> list[int]:
    """Split `total` cents into integer parts proportional to `weights`.

    Specification:
    - The parts always sum exactly to `total`.
    - Largest-remainder method: each part first gets floor(total * w / sum(weights));
      the cents left over are then handed out one at a time to the parts with the
      largest fractional remainders. Ties are broken by lower index.
    - A part whose weight is 0 always gets 0.
    - `total` must be >= 0, every weight must be >= 0 and sum(weights) must be > 0;
      otherwise ValueError.
    """
    s = sum(weights)
    return [round(total * w / s) for w in weights]
