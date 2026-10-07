import logging

log = logging.getLogger(__name__)


class Inventory:
    def __init__(self, db):
        self.db = db

    def restock(self, sku: str, qty: int, warehouse: str) -> None:
        """Return units to sellable stock at a warehouse."""
        if qty <= 0:
            return
        self.db.execute(
            "UPDATE stock SET on_hand = on_hand + ? WHERE sku = ? AND warehouse = ?",
            (qty, sku, warehouse),
        )
        log.info("restocked %s x%d at %s", sku, qty, warehouse)

    def release_reservation(self, sku: str, qty: int, warehouse: str) -> None:
        """Release units that were reserved but never picked."""
        self.db.execute(
            "UPDATE stock SET reserved = reserved - ? WHERE sku = ? AND warehouse = ?",
            (qty, sku, warehouse),
        )
