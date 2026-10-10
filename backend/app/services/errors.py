"""Domain errors raised by the service layer.

They know nothing about HTTP, so the same services can be called from the API, the AI agent's
tools, or scripts. app/api/errors.py maps them to HTTP status codes.
"""


class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    """The request clashes with existing data, e.g. a duplicate name."""


class InvalidStatusTransitionError(ConflictError):
    pass


class BusinessRuleError(DomainError):
    """The request is well-formed but breaks a business rule, e.g. booking an inactive service."""
