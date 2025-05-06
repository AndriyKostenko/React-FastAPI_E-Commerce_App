from fastapi import HTTPException, APIRouter, Depends, status, Request, Header
from typing import Dict, Annotated
import stripe
from src.config import settings
from src.dependencies.dependencies import get_db_session
# from src.routes.user_routes import get_current_user
from src.schemas.order_schemas import PaymentIntentRequest, CreateOrder, UpdateOrder
from src.schemas.payment_schemas import IntentSecret, AddressToUpdate
from src.service.order_service import OrderCRUDService
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.calculate_ttl_amount import calculate_total_amount
from src.security.authentication import auth_manager

stripe.api_key = settings.STRIPE_SECRET_KEY

payment_routes = APIRouter(
    tags=["payments"]
)


@payment_routes.post("/update_payment_intent", response_model=IntentSecret, status_code=status.HTTP_200_OK)
async def update_payment_intent(data: PaymentIntentRequest,
                                current_user: Annotated[dict, Depends(auth_manager.get_current_user)],
                                session: AsyncSession = Depends(get_db_session)):

    print('data>>>>>>>',data)

    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

    # Calculate the total amount in cents
    total_amount = calculate_total_amount(data.items)

    if data.payment_intent_id is not None:
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
                                current_user: Annotated[dict, Depends(auth_manager.get_current_user)],
                                session: AsyncSession = Depends(get_db_session)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

    print(f'Receiveed data>>>>>>>: {data}')
    total_amount = calculate_total_amount(data.items)
    print(f'Total anount>>>>>>',total_amount)

    # creating new intent
    payment_intent = stripe.PaymentIntent.create(
        amount=total_amount,
        currency='cad')

    # the address will be added after the payment is completed after receiving information from the  stripe /webhook
    new_order = {
        "amount": total_amount,
        "currency": 'cad',
        "status": 'pending',
        "delivery_status": 'pending',
        "payment_intent_id": payment_intent.id,
        "products": data.items,
        "user_id": current_user['id']
    }

    # Creating new order
    await OrderCRUDService(session).create_order(CreateOrder(**new_order))

    # Return new order ID and client secret
    return {"payment_intent_id": payment_intent.id,
            "client_secret": payment_intent.client_secret}


@payment_routes.post('/webhook', status_code=status.HTTP_200_OK)
async def webhook(request: Request,
                  current_user: Annotated[dict, Depends(auth_manager.get_current_user)],
                  stripe_signature: str = Header(None),
                  session: AsyncSession = Depends(get_db_session),
                  ):

    if current_user['user_role'] != 'admin' or current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

    data = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=data,
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET
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
