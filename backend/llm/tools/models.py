from dataclasses import dataclass


@dataclass(frozen=True)
class LLMToolDefinition:
    """One tool the LLM is allowed to invoke via tool-use/function-calling.

    input_schema is a JSON Schema object (the same shape an LLM provider's
    tool-use API expects): {"type": "object", "properties": {...},
    "required": [...]}. Instances are immutable -- LLMToolRegistryService
    creates a new instance (via dataclasses.replace) whenever a tool's
    `enabled` state changes via enable()/disable(), so a definition's
    identity, description, and schema never change after registration.
    """

    tool_id: str
    name: str
    description: str
    input_schema: dict
    enabled: bool = True
