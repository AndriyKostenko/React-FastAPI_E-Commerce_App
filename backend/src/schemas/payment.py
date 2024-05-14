from pydantic import BaseModel


class IntentSecret(BaseModel):
    payment_intent_id: str
    client_secret: str
