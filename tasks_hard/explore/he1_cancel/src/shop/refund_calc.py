from .models import Line, Order


def _tax(amount_cents: int, rate_bp: int) -> int:
    # round half up to whole cents
    return (amount_cents * rate_bp + 5000) // 10000


def compute_refund(order: Order, unshipped: list[Line]) -> int:
    """Amount to refund when the unshipped part of an order is cancelled.

    Items: unit price x units not yet shipped.
    Coupon: the fixed coupon is spread over the order in proportion to item value, so
    the cancelled items give back only their share of the discount.
    Shipping: refunded only if nothing at all has shipped.
    Tax: charged on (items - coupon), so it is refunded on the same basis.
    """
    subtotal = sum(l.unit_price_cents * l.qty for l in order.lines)
    cancelled_items = sum(l.unit_price_cents * (l.qty - l.shipped_qty) for l in unshipped)
    if subtotal == 0:
        return 0
    coupon_share = order.coupon_cents * cancelled_items // subtotal
    net = cancelled_items - coupon_share
    refund = net + _tax(net, order.tax_rate_bp)
    if all(l.shipped_qty == 0 for l in order.lines):
        refund += order.shipping_cents
    return max(refund, 0)
