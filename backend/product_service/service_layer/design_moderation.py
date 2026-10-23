"""What the check on a customer's design decides, and the port a moderator implements."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ModerationStage(StrEnum):
    # The customer's words, before any image is paid for.
    PROMPT = "prompt"
    # The generated image, after any cutout, before it is stored and signed.
    IMAGE = "image"


class ModerationCategory(StrEnum):
    """The rules a design can break. Each one is refused; nothing is printed."""

    SEXUAL = "sexual"
    HATE = "hate"
    VIOLENCE = "violence"
    DRUGS = "drugs"
    BRAND = "brand"
    CHARACTER = "character"
    REAL_PERSON = "real_person"

    @property
    def customer_message(self) -> str:
        """What the customer reads; it names the rule, never the model's wording."""
        return _CUSTOMER_MESSAGES[self]


_CUSTOMER_MESSAGES: dict[ModerationCategory, str] = {
    ModerationCategory.SEXUAL: "We can't print this design: it contains sexual or nude content.",
    ModerationCategory.HATE: "We can't print this design: it contains hateful symbols or language.",
    ModerationCategory.VIOLENCE: "We can't print this design: it contains graphic violence.",
    ModerationCategory.DRUGS: "We can't print this design: it promotes drugs.",
    ModerationCategory.BRAND: "We can't print this design: it contains a brand name or logo.",
    ModerationCategory.CHARACTER: "We can't print this design: it shows a copyrighted character.",
    ModerationCategory.REAL_PERSON: "We can't print this design: it shows a real person.",
}


@dataclass(frozen=True, slots=True)
class DesignRefusal:
    """One check's reason for refusing a design."""

    stage: ModerationStage
    category: ModerationCategory
    # The model's own one-sentence reason, for the admin record.
    reason: str
    model: str


class DesignModerationUnavailableError(Exception):
    """No answer this time (provider down, timeout, no key, an answer that does not fit).

    The design is not produced: an unchecked design must never be signed.
    """


class DesignModerator(Protocol):
    """Checks a customer's design before it can be printed."""

    async def check_prompt(self, prompt: str, style: str) -> DesignRefusal | None:
        """None when the request may be drawn. Raises DesignModerationUnavailableError."""
        ...

    async def check_image(self, image_payload: str, prompt: str) -> DesignRefusal | None:
        """None when the image may be printed. Raises DesignModerationUnavailableError."""
        ...


class DesignRefusalLog(Protocol):
    """Keeps each refusal for the admins; the refused image itself is never kept."""

    async def record(self, user_id: UUID | None, prompt: str, style: str, refusal: DesignRefusal) -> None:
        ...
