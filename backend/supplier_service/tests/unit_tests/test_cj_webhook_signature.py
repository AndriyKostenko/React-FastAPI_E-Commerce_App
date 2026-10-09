"""
CJ's webhook signature, checked against the test vector CJ publishes.

"Webhook Mechanism" page, 2026-10: openId 123 and the body below must give
AHxoGFMoS/4mZfJ5vFes5//Pz2QibFQhh3GlrTtnWpk=. If this fails, no genuine push
would ever verify.
"""

import pytest

from schemas.cj_webhook_schemas import CJWebhookSettingsRequest
from service_layer.cj_api_client import (
    CJDropshippingAPIError,
    CJDropshippingWebhookNotEnabledError,
    _rejection,
)
from service_layer.cj_webhook_signature import CJWebhookSignature, InvalidCJWebhookSignature

CJ_OPEN_ID = "123"
CJ_BODY = b'{"messageId":"123111","messageType":"INSERT","params":"123","type":"PRODUCT"}'
CJ_SIGNATURE = "AHxoGFMoS/4mZfJ5vFes5//Pz2QibFQhh3GlrTtnWpk="


def test_cj_published_test_vector() -> None:
    assert CJWebhookSignature(CJ_OPEN_ID).sign(CJ_BODY) == CJ_SIGNATURE
    CJWebhookSignature(CJ_OPEN_ID).verify(CJ_BODY, CJ_SIGNATURE)


@pytest.mark.parametrize(
    "body, signature",
    [
        # The same JSON with its keys in another order is a different body.
        (b'{"type":"PRODUCT","messageId":"123111","messageType":"INSERT","params":"123"}', CJ_SIGNATURE),
        (CJ_BODY + b" ", CJ_SIGNATURE),
        (CJ_BODY, CJ_SIGNATURE[:-2] + "x="),
        (CJ_BODY, None),
        (CJ_BODY, ""),
        (CJ_BODY, "não-ascii"),
    ],
)
def test_anything_but_cjs_exact_signature_is_refused(body: bytes, signature: str | None) -> None:
    with pytest.raises(InvalidCJWebhookSignature):
        CJWebhookSignature(CJ_OPEN_ID).verify(body, signature)


def test_another_accounts_open_id_does_not_verify() -> None:
    with pytest.raises(InvalidCJWebhookSignature):
        CJWebhookSignature("124").verify(CJ_BODY, CJ_SIGNATURE)


def test_an_empty_open_id_is_refused_up_front() -> None:
    with pytest.raises(ValueError):
        CJWebhookSignature("")


def test_registration_turns_stock_and_product_on_and_leaves_orders_to_polling() -> None:
    body = CJWebhookSettingsRequest.stock_only("https://x.example/api/v1/cjdropshipping/webhook", "ENABLE")
    assert body.model_dump(by_alias=True) == {
        "product": {"type": "ENABLE", "callbackUrls": ["https://x.example/api/v1/cjdropshipping/webhook"]},
        "stock": {"type": "ENABLE", "callbackUrls": ["https://x.example/api/v1/cjdropshipping/webhook"]},
        "order": {"type": "CANCEL", "callbackUrls": ["https://x.example/api/v1/cjdropshipping/webhook"]},
        "logistics": {"type": "CANCEL", "callbackUrls": ["https://x.example/api/v1/cjdropshipping/webhook"]},
    }


def test_cj_code_1606010_means_the_product_webhook_is_off() -> None:
    assert isinstance(_rejection(1606010, "Product webhook is not enabled"), CJDropshippingWebhookNotEnabledError)
    assert type(_rejection(1606011, "Subscription limit exceeded")) is CJDropshippingAPIError
