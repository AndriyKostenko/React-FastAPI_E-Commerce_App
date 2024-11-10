from typing import List, Optional

from pydantic import BaseModel


class IntentSecret(BaseModel):
    payment_intent_id: str
    client_secret: str


class AddressToUpdate(BaseModel):
    city: str
    country: str
    line1: str
    line2: Optional[str]
    postal_code: str
    state: str
