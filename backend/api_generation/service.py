from backend.api_documentation_draft import VALIDATED, LLMAPIDocumentationDraft, LLMAPIDocumentationDraftService

from .generator import APIGenerator
from .models import LLMAPIGenerationResult


class DraftNotValidatedError(ValueError):
    """Raised when generate() is given a draft that is not VALIDATED, or that
    differs from the validated draft the draft service holds."""


class InvalidGeneratorOutputError(ValueError):
    """Raised when the generator's output is not a dict of str path -> str content."""


class LLMAPIGenerationService:
    """The only bridge between a validated documentation draft and a generator.

    Reuses LLMAPIDocumentationDraftService as the sole source of truth: the
    draft handed in must be VALIDATED and identical to the one the draft
    service currently holds for its draft_id, so a hand-built or stale copy
    cannot enter generation. An unknown draft_id raises the draft service's
    own UnknownDraftError. The generator is injected as an APIGenerator."""

    def __init__(self, draft_service: LLMAPIDocumentationDraftService, generator: APIGenerator):
        self._draft_service = draft_service
        self._generator = generator

    def generate(self, draft: LLMAPIDocumentationDraft) -> LLMAPIGenerationResult:
        current = self._draft_service.get(draft.draft_id)
        if draft.status != VALIDATED or current.status != VALIDATED or current != draft:
            raise DraftNotValidatedError(draft.draft_id)

        files = self._generator.generate(current)
        if not isinstance(files, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
            raise InvalidGeneratorOutputError(draft.draft_id)
        return LLMAPIGenerationResult(draft_id=current.draft_id, endpoint=current.endpoint, files=dict(files))
