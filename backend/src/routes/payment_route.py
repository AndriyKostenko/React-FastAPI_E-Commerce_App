import math
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import stripe.error

from fastapi import HTTPException, APIRouter, Depends, status, Request, Header
from typing import Dict, Annotated
import stripe
from src.config import settings
from src.db.db_setup import get_db_session
from src.routes.user_routes import get_current_user
from src.schemas.order_schemas import PaymentIntentRequest, CreateOrder, UpdateOrder
from src.schemas.payment import IntentSecret, AddressToUpdate
from src.service.order_service import OrderCRUDService
from sqlalchemy.ext.asyncio import AsyncSession

stripe.api_key = settings.STRIPE_SECRET_KEY

payment_routes = APIRouter(
    tags=["payments"]
)


@payment_routes.post("/update_payment_intent", response_model=IntentSecret, status_code=status.HTTP_200_OK)
async def update_payment_intent(data: PaymentIntentRequest,
                                session: AsyncSession = Depends(get_db_session)):
    # temporary doing to get current user id....suppouse to receive from backend
    current_user_id = 1

    # Calculate the total amount in cents
    total_amount = sum(Decimal(item.price) * Decimal(item.quantity) for item in data.items)
    total_amount = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_amount *= 100  # Convert to cents
    total_amount = int(total_amount)

    if data.payment_intent_id is not None:
        print('---------------ENTERED INTO UPDATE PAYMENT INTENT--------------')
        print('Payment intent ID: ', data.payment_intent_id)
        # Update an order with existing payment intent
        current_intent = stripe.PaymentIntent.retrieve(data.payment_intent_id)

        if current_intent:
            # Update the current payment intent with the new amount
            stripe.PaymentIntent.modify(data.payment_intent_id, amount=total_amount)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid payment intent ID')

        updated_order = {"amount": total_amount,
                         "items": data.items,
                         "payment_intent_id": current_intent.id}

        existing_order = await OrderCRUDService(session).get_order_by_payment_intent_id(payment_intent_id=
                                                                                        current_intent.id)

        if existing_order:
            # updating an order with existing payment intent and new data
            await OrderCRUDService(session).update_order_by_payment_intent_id(
                payment_intent_id=current_intent.id, order=UpdateOrder(**updated_order))

            return {"payment_intent_id": current_intent.id,
                    "client_secret": current_intent.client_secret}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid payment intent ID')
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid payment intent ID')


@payment_routes.post("/create_payment_intent", response_model=IntentSecret, status_code=status.HTTP_201_CREATED)
async def create_payment_intent(data: PaymentIntentRequest,
                                session: AsyncSession = Depends(get_db_session)):
    # TODO: need to check for current user, but I am not sure where to check him...here or on client side
    # and current_user is supposed to be checked on server side...
    # if current_user is None:
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

    # getting current user id from client side
    # if data.current_user_id is None:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid user ID')

    # temporary doing to get current user id....suppouse to receive from backend
    current_user_id = 1

    # Calculate the total amount in cents
    total_amount = sum(Decimal(item.price) * Decimal(item.quantity) for item in data.items)
    total_amount = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_amount *= 100  # Convert to cents
    total_amount = int(total_amount)

    # creating new intent
    payment_intent = stripe.PaymentIntent.create(
        amount=total_amount,
        currency='cad')

    # TODO: need to check how and where to add address
    new_order = {
        "amount": total_amount,
        "currency": 'cad',
        "status": 'pending',
        "delivery_status": 'pending',
        "create_date": datetime.now(),
        "payment_intent_id": payment_intent.id,
        "products": data.items,
        "user_id": current_user_id
    }

    # Creating new order
    await OrderCRUDService(session).create_order(CreateOrder(**new_order))

    # Return new order ID and client secret
    return {"payment_intent_id": payment_intent.id,
            "client_secret": payment_intent.client_secret}


# This is your Stripe CLI webhook secret for testing your endpoint locally.
endpoint_secret = 'whsec_0161353c47a85732f7b8a5e725628e6172f56231cbc91e771a0522506198544f'


@payment_routes.post('/webhook', status_code=status.HTTP_200_OK)
async def webhook(request: Request,
                  stripe_signature: str = Header(None),
                  session: AsyncSession = Depends(get_db_session)):

    data = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=data,
            sig_header=stripe_signature,
            secret=endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail=str(e))

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        address = payment_intent['shipping']['address']

        # updating an order status to 'complete'
        await OrderCRUDService(session).update_status_by_payment_intent_id(payment_intent_id=payment_intent.id,
                                                                           status='complete')

        # updating (creating) an order address
        await OrderCRUDService(session).update_address_by_payment_intent_id(payment_intent_id=payment_intent.id,
                                                                            address=AddressToUpdate(**address))

    else:
        print('Unhandled event type {}'.format(event['type']))
        return {"success": False}

    return {"success": True}
