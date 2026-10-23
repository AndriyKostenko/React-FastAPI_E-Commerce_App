"""
A design moderator with scripted verdicts, standing in for the paid OpenRouter
calls in the generation tests (agreed with the owner). Everything around it
(the quota, the job, the refusal records, the storage) runs for real; the
OpenRouter request itself is covered offline and by the opt-in live test.
"""

from uuid import UUID

from service_layer.design_moderation import (
    DesignModerationUnavailableError,
    DesignRefusal,
    ModerationCategory,
    ModerationStage,
)

type Verdict = DesignRefusal | DesignModerationUnavailableError | None


def refused(
    stage: ModerationStage,
    category: ModerationCategory = ModerationCategory.BRAND,
    reason: str = "It shows a sportswear brand's logo.",
) -> DesignRefusal:
    return DesignRefusal(stage=stage, category=category, reason=reason, model="scripted-moderator")


class ScriptedModerator:
    """A DesignModerator that answers as told (None allows) and remembers what it was shown."""

    def __init__(self, prompt: Verdict = None, image: Verdict = None) -> None:
        self._prompt_verdict = prompt
        self._image_verdict = image
        self.prompts_seen: list[tuple[str, str]] = []
        self.images_seen: list[str] = []

    async def check_prompt(self, prompt: str, style: str) -> DesignRefusal | None:
        self.prompts_seen.append((prompt, style))
        return self._answer(self._prompt_verdict)

    async def check_image(self, image_payload: str, prompt: str) -> DesignRefusal | None:
        self.images_seen.append(image_payload)
        return self._answer(self._image_verdict)

    @staticmethod
    def _answer(verdict: Verdict) -> DesignRefusal | None:
        if isinstance(verdict, DesignModerationUnavailableError):
            raise verdict
        return verdict


class RecordingRefusalLog:
    """A DesignRefusalLog kept in memory, for tests that have no database."""

    def __init__(self) -> None:
        self.records: list[tuple[UUID | None, str, str, DesignRefusal]] = []

    async def record(self, user_id: UUID | None, prompt: str, style: str, refusal: DesignRefusal) -> None:
        self.records.append((user_id, prompt, style, refusal))
