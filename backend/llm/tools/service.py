import copy
import dataclasses

from .models import LLMToolDefinition


class InvalidToolDefinitionError(ValueError):
    """Raised when a tool's name/description/input_schema is malformed."""


class DuplicateToolNameError(InvalidToolDefinitionError):
    """Raised when register() is called with a name that is already registered."""


class UnknownToolError(KeyError):
    """Raised when looking up a tool name that has not been registered."""


class DisabledToolError(Exception):
    """Raised when a disabled tool is looked up via get_invocable()."""


def validate_input_schema(input_schema):
    """Structural check for a tool's JSON Schema input_schema.

    Module-level so that both this registry and LLMToolValidationService
    (backend.llm.tool_validation) enforce the same structural rules from a
    single definition rather than keeping two copies in step. Raises
    InvalidToolDefinitionError; returns None on success.
    """
    if not isinstance(input_schema, dict) or not input_schema:
        raise InvalidToolDefinitionError(
            "input_schema is required and must be a non-empty JSON Schema object"
        )

    if input_schema.get("type") != "object":
        raise InvalidToolDefinitionError("input_schema.type must be 'object'")

    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        raise InvalidToolDefinitionError("input_schema.properties must be an object")

    required = input_schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
        raise InvalidToolDefinitionError("input_schema.required must be a list of strings")

    unknown_required = sorted(set(required) - set(properties))
    if unknown_required:
        raise InvalidToolDefinitionError(
            f"input_schema.required references undeclared propert"
            f"{'y' if len(unknown_required) == 1 else 'ies'}: {unknown_required}"
        )


class LLMToolRegistryService:
    """Catalogs the tools an LLM is permitted to call via tool-use/function-calling.

    This service only registers, looks up, lists, and enables/disables tool
    definitions -- it never calls a tool. Dispatching an actual invocation
    (running the underlying service a tool describes) is out of scope here
    and belongs to a later commit; get_invocable() exists only so that
    future dispatch code has one place to enforce "disabled tools cannot be
    invoked" without this service executing anything itself.
    """

    def __init__(self):
        self._tools = {}
        self._id_by_name = {}
        self._tool_counter = 0

    def register(
        self, name: str, description: str, input_schema: dict, enabled: bool = True
    ) -> LLMToolDefinition:
        if not name or not isinstance(name, str):
            raise InvalidToolDefinitionError("name is required")

        if not description or not isinstance(description, str):
            raise InvalidToolDefinitionError("description is required")

        if name in self._id_by_name:
            raise DuplicateToolNameError(f"tool name {name!r} is already registered")

        validate_input_schema(input_schema)

        self._tool_counter += 1
        tool = LLMToolDefinition(
            tool_id=f"tool-{self._tool_counter}",
            name=name,
            description=description,
            # Store a defensive copy so a caller mutating the dict it passed
            # in afterward can never reach into a registered definition.
            input_schema=copy.deepcopy(input_schema),
            enabled=bool(enabled),
        )

        self._tools[tool.tool_id] = tool
        self._id_by_name[name] = tool.tool_id
        return tool

    def _resolve_id(self, name: str) -> str:
        try:
            return self._id_by_name[name]
        except KeyError:
            raise UnknownToolError(name)

    def get(self, name: str) -> LLMToolDefinition:
        """Raw lookup by name -- returns the tool regardless of enabled state."""
        return self._tools[self._resolve_id(name)]

    def get_invocable(self, name: str) -> LLMToolDefinition:
        """Lookup for callers about to dispatch a tool-use request.

        Raises DisabledToolError if the tool is disabled. This registry
        still never invokes anything -- it only gates the lookup a future
        dispatcher would use.
        """
        tool = self.get(name)
        if not tool.enabled:
            raise DisabledToolError(f"tool {name!r} is disabled and cannot be invoked")
        return tool

    def list(self, enabled_only: bool = False) -> list:
        tools = list(self._tools.values())
        if enabled_only:
            tools = [tool for tool in tools if tool.enabled]
        return tools

    def enable(self, name: str) -> LLMToolDefinition:
        return self._set_enabled(name, True)

    def disable(self, name: str) -> LLMToolDefinition:
        return self._set_enabled(name, False)

    def _set_enabled(self, name: str, enabled: bool) -> LLMToolDefinition:
        tool_id = self._resolve_id(name)
        updated = dataclasses.replace(self._tools[tool_id], enabled=enabled)
        self._tools[tool_id] = updated
        return updated
