from abc import ABC, abstractmethod

from backend.api_documentation_draft import LLMAPIDocumentationDraft


class APIGenerator(ABC):
    """The contract a future application generator satisfies. Its only input
    is an existing, VALIDATED LLMAPIDocumentationDraft; it returns a mapping
    of relative file path to text content. LLMAPIGenerationService is the
    only caller, so a generator never sees an unvalidated draft."""

    @abstractmethod
    def generate(self, draft: LLMAPIDocumentationDraft) -> dict:
        ...
