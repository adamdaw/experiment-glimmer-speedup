from dataclasses import dataclass, field
from enum import Enum


class Status(Enum):
    PLACED = "placed"
    PARTIALLY_SHIPPED = "partially_shipped"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    PARTIALLY_CANCELLED = "partially_cancelled"


@dataclass
class Line:
    sku: str
    qty: int
    unit_price_cents: int
    shipped_qty: int = 0
    warehouse: str = "main"


@dataclass
class Order:
    id: str
    customer_id: str
    lines: list[Line]
    status: Status
    shipping_cents: int
    coupon_cents: int = 0          # fixed discount applied to the whole order
    tax_rate_bp: int = 0           # tax in basis points (e.g. 825 = 8.25%)
    payment_id: str | None = None
    history: list[str] = field(default_factory=list)
