from ..tools import (
    InvalidToolDefinitionError,
    LLMToolDefinition,
    LLMToolRegistryService,
    validate_input_schema,
)
from .models import (
    ENUM,
    MAXIMUM,
    MINIMUM,
    REQUIRED,
    TYPE,
    UNKNOWN_FIELD,
    LLMToolValidationError,
)

# JSON Schema type names a tool's properties may declare, mapped to the check
# that decides whether a value matches. bool is tested before int because
# bool is an int subclass in Python -- the same ordering backend.input_validation
# uses in its own _matches_type.
_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}

_NUMERIC_TYPES = frozenset({"integer", "number"})


class ToolArgumentValidationError(ValueError):
    """Raised by validate_arguments() when arguments don't match a tool's schema.

    Carries the full list of LLMToolValidationError entries -- like
    backend.input_validation.ValidationFailedError, so a caller can report
    every problem at once rather than only the first. Arguments that raise
    this must never be executed.
    """

    def __init__(self, tool_name: str, errors: list):
        self.tool_name = tool_name
        self.errors = errors
        summary = "; ".join(
            f"{error.field or '<arguments>'} ({error.rule}): {error.message}"
            for error in errors
        )
        super().__init__(f"arguments for tool {tool_name!r} failed validation: {summary}")


class LLMToolValidationService:
    """Validates tool definitions and LLM-produced tool arguments (Commit #2).

    Sits between Commit #1's LLMToolRegistryService and any future dispatcher:
    the registry says which tools exist and which are enabled, this service
    says whether a given set of LLM-produced arguments is safe to hand on.
    It reuses the registry as the single source of truth for both -- tool
    lookup and the enabled check go through registry.get_invocable(), and
    the structural schema check is the registry's own validate_input_schema,
    not a second copy of those rules.

    Like the registry, this service never invokes a tool. It reads
    definitions and inspects argument dicts; it has no dispatch surface and
    never calls the underlying capability a tool describes.
    """

    def __init__(self, registry: LLMToolRegistryService):
        self._registry = registry

    def validate_definition(self, tool: LLMToolDefinition) -> bool:
        """Check one tool definition, structure and declared property types.

        Structure (input_schema is a non-empty JSON Schema object, properties
        is an object, required is a list of declared property names) is
        delegated to the registry's validate_input_schema. On top of that
        this adds the per-property checks a registry entry doesn't make:
        every property must be an object declaring a known JSON Schema type.
        Raises InvalidToolDefinitionError; returns True on success.
        """
        if not isinstance(tool, LLMToolDefinition):
            raise InvalidToolDefinitionError(
                "tool must be an LLMToolDefinition"
            )

        if not tool.name or not isinstance(tool.name, str):
            raise InvalidToolDefinitionError("name is required")

        if not tool.description or not isinstance(tool.description, str):
            raise InvalidToolDefinitionError("description is required")

        validate_input_schema(tool.input_schema)

        for field, spec in tool.input_schema["properties"].items():
            if not isinstance(spec, dict):
                raise InvalidToolDefinitionError(
                    f"property {field!r} must be a JSON Schema object"
                )

            declared_type = spec.get("type")
            if declared_type is None:
                raise InvalidToolDefinitionError(
                    f"property {field!r} must declare a type"
                )

            if declared_type not in _TYPE_CHECKS:
                raise InvalidToolDefinitionError(
                    f"property {field!r} declares unknown type {declared_type!r}. "
                    f"Known types: {sorted(_TYPE_CHECKS)}"
                )

            if ENUM in spec and not isinstance(spec[ENUM], list):
                raise InvalidToolDefinitionError(
                    f"property {field!r} enum must be a list"
                )

        return True

    def _resolve(self, tool_name: str) -> LLMToolDefinition:
        """Registered-and-enabled lookup, then a definition check.

        get_invocable() is the registry's own gate -- it raises
        UnknownToolError for a name that was never registered and
        DisabledToolError for one that is disabled, so a disabled tool's
        arguments are never even inspected, let alone executed.
        """
        tool = self._registry.get_invocable(tool_name)
        self.validate_definition(tool)
        return tool

    def errors(self, tool_name: str, arguments: dict) -> list:
        """Return every way `arguments` fails `tool_name`'s schema, as a list.

        An empty list means the arguments match. Raises (rather than
        returning an error entry) when the tool itself is unusable --
        unknown, disabled, or malformed -- mirroring how
        backend.input_validation.violations() raises for an unknown
        candidate_id: those are caller bugs, not argument problems.
        """
        tool = self._resolve(tool_name)
        schema = tool.input_schema
        found = []

        if not isinstance(arguments, dict):
            return [
                LLMToolValidationError(
                    tool_name=tool_name,
                    field=None,
                    rule=TYPE,
                    value="object",
                    message=(
                        f"arguments must be an object, got "
                        f"{type(arguments).__name__}"
                    ),
                )
            ]

        properties = schema["properties"]
        required = schema.get("required", [])

        for field in required:
            if field not in arguments:
                found.append(
                    LLMToolValidationError(
                        tool_name=tool_name,
                        field=field,
                        rule=REQUIRED,
                        value=None,
                        message=f"{field!r} is required",
                    )
                )

        if not schema.get("additionalProperties", False):
            for field in arguments:
                if field not in properties:
                    found.append(
                        LLMToolValidationError(
                            tool_name=tool_name,
                            field=field,
                            rule=UNKNOWN_FIELD,
                            value=None,
                            message=(
                                f"{field!r} is not declared by tool "
                                f"{tool_name!r}"
                            ),
                        )
                    )

        for field, spec in properties.items():
            if field not in arguments:
                continue

            value = arguments[field]
            declared_type = spec["type"]

            if not _TYPE_CHECKS[declared_type](value):
                found.append(
                    LLMToolValidationError(
                        tool_name=tool_name,
                        field=field,
                        rule=TYPE,
                        value=declared_type,
                        message=(
                            f"{field!r} must be of type {declared_type}, got "
                            f"{type(value).__name__}"
                        ),
                    )
                )
                # Every remaining check assumes the declared type held.
                continue

            if ENUM in spec and value not in spec[ENUM]:
                found.append(
                    LLMToolValidationError(
                        tool_name=tool_name,
                        field=field,
                        rule=ENUM,
                        value=spec[ENUM],
                        message=(
                            f"{field!r} must be one of {spec[ENUM]!r}, got "
                            f"{value!r}"
                        ),
                    )
                )

            if declared_type in _NUMERIC_TYPES:
                if MINIMUM in spec and value < spec[MINIMUM]:
                    found.append(
                        LLMToolValidationError(
                            tool_name=tool_name,
                            field=field,
                            rule=MINIMUM,
                            value=spec[MINIMUM],
                            message=(
                                f"{field!r} must be >= {spec[MINIMUM]}, got {value}"
                            ),
                        )
                    )

                if MAXIMUM in spec and value > spec[MAXIMUM]:
                    found.append(
                        LLMToolValidationError(
                            tool_name=tool_name,
                            field=field,
                            rule=MAXIMUM,
                            value=spec[MAXIMUM],
                            message=(
                                f"{field!r} must be <= {spec[MAXIMUM]}, got {value}"
                            ),
                        )
                    )

        return found

    def validate_arguments(self, tool_name: str, arguments: dict) -> bool:
        """Raise unless `arguments` are safe to hand to `tool_name`.

        Returns True only when the tool is registered, enabled, well-defined,
        and every argument matches its declared schema. Raises
        ToolArgumentValidationError carrying all errors otherwise. This is
        the check a dispatcher runs before execution -- it performs none
        itself.
        """
        found = self.errors(tool_name, arguments)
        if found:
            raise ToolArgumentValidationError(tool_name, found)
        return True
