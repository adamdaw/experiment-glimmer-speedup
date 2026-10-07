class Notifier:
    def __init__(self, mailer, warehouse_queue):
        self.mailer = mailer
        self.warehouse_queue = warehouse_queue

    def order_cancelled(self, order, refund_cents: int, actor: str) -> None:
        # Tell the warehouse to stop picking whatever has not shipped yet.
        pending = [(l.sku, l.qty - l.shipped_qty) for l in order.lines if l.shipped_qty < l.qty]
        if pending:
            self.warehouse_queue.publish("cancel_pick", {"order_id": order.id, "lines": pending})
        # Customer email; staff-initiated cancellations use a different template.
        template = "cancel_by_staff" if actor == "staff" else "cancel_confirmation"
        self.mailer.send(order.customer_id, template, {
            "order_id": order.id,
            "refund": f"{refund_cents / 100:.2f}",
            "partial": order.status.value == "partially_cancelled",
        })
