from dataclasses import dataclass


@dataclass(frozen=True)
class LLMPromptTemplate:
    """A single immutable, versioned prompt template.

    Instances are never mutated after creation -- LLMPromptTemplateService
    creates a new instance (via dataclasses.replace) whenever a version's
    `enabled` state changes, so every version's template text is permanent.
    """

    template_id: str
    name: str
    version: int
    template: str
    variables: tuple
    enabled: bool = False
