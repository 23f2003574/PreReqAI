from dataclasses import dataclass
from datetime import datetime


@dataclass
class LLMAPIDocumentation:
    """One generated version of an API candidate's documentation.

    parameters/response are always rebuilt directly from the Commit #4/#5
    schemas (never left to the LLM to restate), so they can never drift into
    an unsupported claim. summary/description/examples come from the LLM,
    but every example is checked against the same schemas before this record
    is created. Each generate()/update() call produces a new, immutable
    snapshot -- generated_at orders the versions for a given candidate_id.
    """

    candidate_id: str
    summary: str
    description: str
    parameters: dict
    response: dict
    examples: list
    generated_at: datetime
