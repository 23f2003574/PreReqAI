from dataclasses import dataclass


ALLOWED_TYPES = frozenset({"int", "float", "str", "bool", "list", "dict", "tuple"})
STRUCTURED_TYPES = frozenset({"list", "dict"})


@dataclass
class LLMOutputSchema:
    """The inferred structured output (response) schema for one API candidate.

    fields preserves the candidate's original output order. types/nullable/
    structure are all keyed (or, for nullable, listed) by field name --
    structure only carries a non-empty descriptor for "list"/"dict" fields
    (see LLMOutputSchemaService.validate).
    """

    candidate_id: str
    fields: list
    types: dict
    nullable: list
    structure: dict
