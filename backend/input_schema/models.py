from dataclasses import dataclass


ALLOWED_TYPES = frozenset({"int", "float", "str", "bool", "list", "dict", "tuple"})


@dataclass
class LLMInputSchema:
    """The inferred structured input schema for one API candidate.

    fields preserves the candidate's original input order. types/required/
    defaults/constraints are all keyed by field name -- types must cover
    every field, required and defaults are consistent subsets of fields
    (see LLMInputSchemaService.validate).
    """

    candidate_id: str
    fields: list
    types: dict
    required: list
    defaults: dict
    constraints: dict
