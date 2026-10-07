class BillingError(Exception):
    """Base class for billing errors."""


class CurrencyMismatch(BillingError):
    pass


class OverRefund(BillingError):
    pass


class IdempotencyConflict(BillingError):
    pass


class NotPaid(BillingError):
    pass
