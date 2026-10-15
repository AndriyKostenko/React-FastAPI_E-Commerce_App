"""The parcel an order line left in, as each fulfillment channel reports it."""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ParcelTracking:
    tracking_number: str
    carrier: str | None
    tracking_url: str | None
    shipped_at: datetime

    @staticmethod
    def parse_time(value: str | datetime | None) -> datetime:
        """A channel's shipped time: a datetime, an ISO string, or now when absent or unreadable."""
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                pass
        return datetime.now(UTC)
