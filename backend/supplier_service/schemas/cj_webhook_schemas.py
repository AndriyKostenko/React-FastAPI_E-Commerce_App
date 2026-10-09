"""CJ Dropshipping webhook payloads: what CJ pushes to us and how we register for it.

Shapes from CJ's "Webhook Mechanism" and "08. Webhook" pages (2026-10).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel


class CJWebhookTopic(StrEnum):
    """A push's ``type``. PRODUCT and VARIANT arrive because stock needs the product topic on."""

    PRODUCT = "PRODUCT"
    VARIANT = "VARIANT"
    STOCK = "STOCK"
    ORDER = "ORDER"
    LOGISTIC = "LOGISTIC"  # sic: what CJ sends (seen 2026-10-09)


class CJWebhookMessage(BaseModel):
    """The envelope every push shares. ``params`` depends on the topic and is parsed per topic."""

    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId")
    type: str
    message_type: str | None = Field(default=None, alias="messageType")
    params: JsonValue = None


class CJStockRow(BaseModel):
    """One warehouse's stock of one variant, as a STOCK push reports it."""

    model_config = ConfigDict(populate_by_name=True)

    vid: str
    area_id: str | None = Field(default=None, alias="areaId")
    area_en: str | None = Field(default=None, alias="areaEn")
    country_code: str | None = Field(default=None, alias="countryCode")
    storage_num: int = Field(default=0, alias="storageNum")


class CJStockParams(RootModel[dict[str, list[CJStockRow]]]):
    """A STOCK push's ``params``: variant id -> that variant's warehouse rows."""


class CJWebhookAck(BaseModel):
    """What we answer a push with: CJ's own sample reply. Only the 200 status matters to CJ."""

    code: int = 200
    result: str = "success"
    message: str = "ok"


# --------------------------------------------------------------- registration

CJWebhookSwitch = Literal["ENABLE", "CANCEL"]


class CJWebhookTopicSetting(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: CJWebhookSwitch
    # CJ accepts exactly one URL per topic.
    callback_urls: list[str] = Field(alias="callbackUrls", min_length=1, max_length=1)


class CJWebhookSettingsRequest(BaseModel):
    """Body of ``POST /webhook/set``. CJ requires all four topics in every call."""

    product: CJWebhookTopicSetting
    stock: CJWebhookTopicSetting
    order: CJWebhookTopicSetting
    logistics: CJWebhookTopicSetting

    @classmethod
    def stock_only(cls, callback_url: str, switch: CJWebhookSwitch) -> "CJWebhookSettingsRequest":
        """
        Stock pushes on (or off), with the product topic alongside them.

        CJ refuses to subscribe products while the product topic is off, so
        the two go together. Orders and logistics stay off: tracking is polled.
        """
        on = CJWebhookTopicSetting(type=switch, callback_urls=[callback_url])
        off = CJWebhookTopicSetting(type="CANCEL", callback_urls=[callback_url])
        return cls(product=on, stock=on, order=off, logistics=off)


class CJProductSubscriptionResult(BaseModel):
    """``data`` of ``POST /webhook/product/subscribe``."""

    model_config = ConfigDict(populate_by_name=True)

    success_product_ids: list[str] = Field(default_factory=list, alias="successProductIds")
    # CJ's docs list "already subscribed" here too, but live (2026-10-09) a
    # repeat subscription came back as a success; "no such product" and an
    # account over its cap are what is left.
    fail_product_ids: list[str] = Field(default_factory=list, alias="failProductIds")
