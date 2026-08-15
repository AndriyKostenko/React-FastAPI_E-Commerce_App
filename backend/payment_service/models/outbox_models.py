from shared.models.outbox_events import OutboxEventMixin
from models.base import Base


class OutboxEvent(OutboxEventMixin, Base):
    __tablename__ = "outbox_events"
