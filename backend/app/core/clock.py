from datetime import UTC, datetime


def now() -> datetime:
    """The current time (UTC). Wrapped in a function so tests can freeze it."""
    return datetime.now(UTC)
