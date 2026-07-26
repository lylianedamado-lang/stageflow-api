from datetime import datetime, timezone


def utcnow() -> datetime:
    """Horodatage courant en UTC, avec fuseau explicite."""
    return datetime.now(timezone.utc)
