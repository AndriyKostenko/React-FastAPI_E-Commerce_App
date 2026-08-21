from models.base import Base
from shared.models.outbox_events import OutboxEventMixin


class OutboxEvent(OutboxEventMixin, Base):
    __tablename__ = "outbox_events"

