from .errors import Forbidden, NotFound
from .orders import OrderService


def cancel_order_handler(request, service: OrderService):
    """POST /orders/<id>/cancel  body: {"reason": "..."}"""
    order_id = request.path_params["id"]
    order = service.repo.get(order_id)
    if order is None:
        raise NotFound(order_id)
    if order.customer_id != request.user.id and not request.user.is_staff:
        raise Forbidden("not your order")
    reason = (request.json or {}).get("reason", "customer request")[:200]
    actor = "staff" if request.user.is_staff else "customer"
    result = service.cancel(order_id, reason=reason, actor=actor)
    return {"status": result.status.value, "refund_cents": result.refund_cents}
