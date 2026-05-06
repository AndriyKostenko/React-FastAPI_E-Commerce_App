from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID


class PaymentSchema(BaseModel):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    amount: int  # in cents
    currency: str

    model_config = ConfigDict(from_attributes=True)
