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
    if total < 0 or any(w < 0 for w in weights) or sum(weights) <= 0:
        raise ValueError("bad allocate arguments")
    s = sum(weights)
    base = [total * w // s for w in weights]
    rem = [total * w % s for w in weights]
    left = total - sum(base)
    order = sorted(range(len(weights)), key=lambda i: (-rem[i], i))
    for i in order[:left]:
        base[i] += 1
    return base
