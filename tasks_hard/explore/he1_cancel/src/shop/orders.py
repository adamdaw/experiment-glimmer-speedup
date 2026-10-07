from dataclasses import dataclass

from .errors import Conflict
from .models import Order, Status
from .refund_calc import compute_refund


@dataclass
class CancelResult:
    status: Status
    refund_cents: int


class OrderService:
    def __init__(self, repo, inventory, payments, notifier):
        self.repo = repo
        self.inventory = inventory
        self.payments = payments
        self.notifier = notifier

    def cancel(self, order_id: str, reason: str, actor: str) -> CancelResult:
        order: Order = self.repo.get_for_update(order_id)
        if order.status in (Status.DELIVERED, Status.CANCELLED, Status.PARTIALLY_CANCELLED):
            raise Conflict(f"order {order_id} is {order.status.value}")
        if order.status is Status.SHIPPED:
            raise Conflict("order already shipped; use a return instead")

        unshipped = [l for l in order.lines if l.shipped_qty < l.qty]
        for line in unshipped:
            self.inventory.restock(line.sku, line.qty, line.warehouse)

        refund_cents = compute_refund(order, unshipped)
        if refund_cents > 0 and order.payment_id:
            self.payments.refund(order.payment_id, refund_cents, key=f"cancel-{order.id}")

        anything_shipped = any(l.shipped_qty > 0 for l in order.lines)
        order.status = Status.PARTIALLY_CANCELLED if anything_shipped else Status.CANCELLED
        order.history.append(f"cancelled by {actor}: {reason}")
        self.repo.save(order)

        self.notifier.order_cancelled(order, refund_cents, actor)
        return CancelResult(order.status, refund_cents)
