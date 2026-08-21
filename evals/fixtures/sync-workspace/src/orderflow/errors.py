"""Error taxonomy for the order pipeline.

The split matters operationally: dispatch and storage retry RetryableError
subclasses only. FatalError subclasses fail the order immediately.
"""


class OrderError(Exception):
    """Base class for all pipeline errors."""


class FatalError(OrderError):
    """Non-recoverable. The pipeline must not retry these."""


class RetryableError(OrderError):
    """Transient. Safe to retry with backoff."""


class ValidationError(FatalError):
    """The incoming order payload is malformed or violates business rules."""


class UnknownSku(FatalError):
    """A line item references a SKU that is not in the catalog."""


class InsufficientStock(FatalError):
    """The catalog does not hold enough stock to reserve the order."""


class VersionConflict(RetryableError):
    """Optimistic concurrency check failed while writing to the store."""


class CarrierTimeout(RetryableError):
    """The carrier API did not answer in time."""


class CarrierUnavailable(RetryableError):
    """The carrier API answered with a transient 5xx-style failure."""
