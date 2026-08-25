from dataclasses import dataclass

DRAFT = "DRAFT"
VALIDATED = "VALIDATED"
STATUSES = frozenset({DRAFT, VALIDATED})


@dataclass(frozen=True)
class LLMAPIDocumentationDraft:
    """One reviewable documentation draft for a Commit #4 recommendation whose
    Commit #5 schema review was APPROVED.

    parameters/responses/examples are never generated independently here --
    they are read straight from backend.api_documentation's own
    schema-grounded, example-validated LLMAPIDocumentation record (from the
    original notebook-to-API series), so this draft can never drift into an
    unsupported claim the existing documentation service wouldn't already
    have rejected. status starts DRAFT and becomes VALIDATED once
    validate() re-confirms the draft against the current schemas. Drafting
    never modifies generated API/OpenAPI output.
    """

    draft_id: str
    endpoint: str
    summary: str
    description: str
    parameters: dict
    responses: dict
    examples: list
    status: str
