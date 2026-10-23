from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignRefusalAdminSchema(BaseModel):
    """One refused design, as the admins see it."""

    id: UUID
    user_id: UUID | None
    stage: str
    category: str
    prompt: str
    style: str
    reason: str
    model: str
    date_created: datetime

    model_config = ConfigDict(from_attributes=True)
