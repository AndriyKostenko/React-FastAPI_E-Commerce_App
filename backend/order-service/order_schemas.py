# from datetime import datetime
# from typing import Optional, List

# from pydantic import BaseModel, ConfigDict
# from pydantic.fields import Field

# from src.schemas.product_schemas import ProductSchema



# class CreateOrder(BaseModel):
#     amount: float
#     currency: str
#     status: str
#     delivery_status: str
#     payment_intent_id: str
#     products: List[ProductSchema]
#     # TODO: need to check how and where to add address
#     # address: List[AddressType]
#     user_id: str


# class UpdateOrder(BaseModel):
#     delivery_status: Optional[str] = None
#     status: Optional[str] = None
#     amount: float


# class PaymentIntentRequest(BaseModel):
#     items: List[ProductSchema]
#     payment_intent_id: Optional[str]
