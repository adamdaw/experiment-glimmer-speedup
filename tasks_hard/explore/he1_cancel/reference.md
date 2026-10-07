Key facts (with the lines that support them). Graders: a citation is **correct** if the cited lines support the claim, **wrong** if the lines exist but do not support it, and **hallucinated** if the file or line does not exist (or describes code that is not shown).

Flow and permissions
- api.py:5-16 cancel_order_handler: loads the order (8), 404 if missing (9-10), 403 unless owner or staff (11-12); reason from body, default "customer request", truncated to 200 chars (13); actor = "staff"/"customer" (14); calls service.cancel (15); returns status value + refund_cents (16).
- orders.py:21-42 OrderService.cancel: re-loads with get_for_update (22); rejects DELIVERED/CANCELLED/PARTIALLY_CANCELLED (23-24) and SHIPPED (25-26) with Conflict. So only PLACED and PARTIALLY_SHIPPED can be cancelled.
- Order of effects: restock (28-30) -> compute_refund (32) -> payments.refund with key "cancel-<order id>" only if refund > 0 and payment_id set (33-34) -> status (36-37) -> history append (38) -> repo.save (39) -> notifier.order_cancelled (41) -> CancelResult (42).
- End state: PARTIALLY_CANCELLED if any line has shipped_qty > 0, else CANCELLED (36-37). For the scenario (some items shipped): PARTIALLY_CANCELLED.

Refund (refund_calc.py:9-27)
- subtotal = sum(unit_price * qty) over ALL lines (18); cancelled_items = unit_price * (qty - shipped_qty) over unshipped lines (19); returns 0 if subtotal == 0 (20-21).
- coupon share = coupon_cents * cancelled_items // subtotal, floor division (22) -> rounds the clawed-back discount DOWN (customer gets up to 1 cent more).
- net = items - coupon share (23); tax = round-half-up of net * rate_bp / 10000 (4-6, 24).
- shipping refunded only if no line has shipped anything (25-26) -> in this scenario shipping is NOT refunded.
- result clamped at >= 0 (27).

Inventory
- BUG: orders.py:30 restocks line.qty (the full ordered quantity) for every line that is not fully shipped, not qty - shipped_qty -> shipped units are put back into on_hand stock (phantom inventory / overselling). Compare notify.py:8, which correctly uses qty - shipped_qty.
- restock adds to on_hand via UPDATE (inventory.py:10-18), no-op for qty <= 0 (12-13).
- release_reservation (inventory.py:20-25) exists but is never called by cancel -> reserved counts are never released (likely bug; depends on the reservation model).

Notifications (notify.py:6-17)
- warehouse "cancel_pick" message with (sku, qty - shipped_qty) for lines not fully shipped, only if any (8-10).
- customer email: template "cancel_by_staff" if actor == "staff" else "cancel_confirmation" (12); payload includes order id, refund formatted as a decimal string, and partial = status is partially_cancelled (13-17).

Other risky behavior (credit if correct and cited)
- The payment refund (34) happens before repo.save (39): if save fails, money is refunded but the order stays cancellable; a retry reuses the same key "cancel-<id>", which protects only if the payment provider de-duplicates on it. Restock (30) is also done before, and is not idempotent.
- Notifications are sent after save and outside any shown transaction; a notifier failure would surface as an error after the cancel already took effect.
- Staff can cancel any customer's order (11).
- api.py:13: a JSON body with "reason": null would raise (None[:200]).
- The handler reads the order without a lock (8) before the service re-reads it for update (22) - benign.

Not in the code (hallucination if claimed as fact): any restocking fee, any partial-shipment refund of shipping, any tax on shipping, any email to the warehouse, calls to release_reservation, database transactions/rollbacks around cancel.
