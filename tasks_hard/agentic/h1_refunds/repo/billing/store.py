from .invoice import Invoice


class InMemoryStore:
    """Stand-in for the database. Refunds are stored by refund_id."""

    def __init__(self):
        self.invoices: dict[str, Invoice] = {}
        self.refunds: dict[str, "object"] = {}

    def add_invoice(self, invoice: Invoice) -> None:
        self.invoices[invoice.invoice_id] = invoice

    def get_invoice(self, invoice_id: str) -> Invoice:
        return self.invoices[invoice_id]

    def save_refund(self, refund) -> None:
        self.refunds[refund.refund_id] = refund

    def refunds_for(self, invoice_id: str) -> list:
        return [r for r in self.refunds.values() if r.invoice_id == invoice_id]
