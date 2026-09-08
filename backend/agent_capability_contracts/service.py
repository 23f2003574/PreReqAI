from backend.agent_capability_registry import LLMAgentCapabilityRegistry

from .in_memory_store import InMemoryContractStore
from .models import (
    CHECK_INPUT,
    CHECK_OUTPUT,
    CHECK_REQUIREMENTS,
    ENUM,
    MAXIMUM,
    MINIMUM,
    MISSING_CONTEXT,
    REQUIRED,
    REQUIREMENT_NOT_MET,
    TYPE,
    UNKNOWN_FIELD,
    InvalidCapabilityContractError,
    LLMAgentCapabilityContract,
    LLMAgentCapabilityContractCheck,
    LLMAgentCapabilityContractViolation,
)
from .store import ContractStore

# JSON Schema type names a contract's schema properties may declare, and the
# check that decides whether a value matches -- the exact same map
# backend.llm.tool_validation.LLMToolValidationService keeps privately for
# tool arguments (bool checked before int, since bool is an int subclass in
# Python), mirrored locally here rather than reached into across module
# boundaries: it is a small, same-shape reimplementation, the same
# precedent backend.agent_risk_profile.constraints_met already set for
# reusing a shape across unrelated domains without a private cross-module
# import.
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


class DuplicateContractError(InvalidCapabilityContractError):
    """Raised when register() is given a (capability_id, version) pair
    that already has a registered contract -- a contract is immutable
    once registered, so this is rejected outright rather than silently
    overwritten (Rule: "contract changes must not silently invalidate
    existing versions")."""


class UnknownContractError(KeyError):
    """Raised when get()/validate_input()/validate_output()/
    check_requirements() finds no contract for the requested
    (capability_id, version) -- including when version=None and no
    contract has been registered yet for that capability's current
    LLMAgentCapabilityRegistry version."""


class LLMAgentCapabilityContractService:
    """Registers and retrieves immutable, versioned contracts describing
    what a Commit #1 LLMAgentCapability accepts, produces, and requires,
    and validates payloads/context against them.

    Not a parallel schema system: structural and payload-level schema
    checking both reuse backend.llm.tools.validate_input_schema and the
    exact same {"type", "properties", "required", "enum", "minimum",
    "maximum"} JSON Schema vocabulary
    backend.llm.tool_validation.LLMToolValidationService already
    validates tool arguments against -- input_schema/output_schema
    payload checks below mirror that service's own errors() algorithm
    exactly, adapted from tool arguments to an arbitrary payload/response
    dict. Capability existence is entirely Commit #1's own
    LLMAgentCapabilityRegistry -- register() rejects a contract for a
    capability_id that was never registered there (propagating Commit
    #1's own UnknownCapabilityError, never a second "unknown capability"
    check), and get(capability_id, version=None) resolves "current" by
    reading that same registry's own live LLMAgentCapability.version,
    never a separately maintained "latest" pointer.

    No capability execution happens anywhere in this service: validation
    only ever inspects a payload/context dict a caller already produced,
    it never calls the capability an LLMAgentCapability/contract
    describes. Every read method (get(), validate_input(),
    validate_output(), check_requirements()) is side-effect free -- none
    of them mutate the registry, a stored contract, or anything they are
    given.
    """

    def __init__(self, capability_registry: LLMAgentCapabilityRegistry, store: ContractStore = None):
        self._capability_registry = capability_registry
        self.store = store if store is not None else InMemoryContractStore()

    def register(self, contract) -> LLMAgentCapabilityContract:
        """Register an immutable contract for a registered capability's
        (capability_id, version).

        contract may be an LLMAgentCapabilityContract instance or an
        equivalent dict; either way its own fields are validated by
        LLMAgentCapabilityContract's own __post_init__ before anything
        else runs.

        Raises:
            InvalidCapabilityContractError: If contract is not an
                LLMAgentCapabilityContract or dict, or its own fields
                fail validation
            UnknownCapabilityError: If contract.capability_id was never
                registered in the Commit #1 capability registry
                (propagated unchanged, not wrapped)
            DuplicateContractError: If a contract already exists for this
                exact (capability_id, version) pair
        """
        resolved = self._resolve_contract(contract)

        # Rule: "reject contracts for unknown capabilities" -- Commit
        # #1's own registry is the single source of truth for whether
        # capability_id exists; its own UnknownCapabilityError propagates
        # unchanged rather than being re-derived or wrapped here.
        self._capability_registry.get(resolved.capability_id)

        if self.store.get(resolved.capability_id, resolved.version) is not None:
            raise DuplicateContractError(
                f"a contract for capability {resolved.capability_id!r} version "
                f"{resolved.version!r} is already registered"
            )

        return self.store.save(resolved)

    def get(self, capability_id: str, version: str = None) -> LLMAgentCapabilityContract:
        """The contract for capability_id at version, or -- version=None
        -- at the capability's own current LLMAgentCapabilityRegistry
        version.

        Raises:
            UnknownCapabilityError: If capability_id was never registered
                in the Commit #1 capability registry
            UnknownContractError: If no contract is registered for the
                resolved (capability_id, version) pair
        """
        capability = self._capability_registry.get(capability_id)
        resolved_version = version if version is not None else capability.version

        contract = self.store.get(capability_id, resolved_version)
        if contract is None:
            raise UnknownContractError(
                f"no contract registered for capability {capability_id!r} version {resolved_version!r}"
            )
        return contract

    def validate_input(self, capability_id: str, payload) -> LLMAgentCapabilityContractCheck:
        """Check payload against capability_id's current contract's
        input_schema. Never raises for a payload that fails -- every
        mismatch is collected into the returned check's violations.

        Raises:
            UnknownCapabilityError, UnknownContractError: As get()
        """
        contract = self.get(capability_id)
        violations = self._schema_violations(contract, contract.input_schema, payload, CHECK_INPUT)
        return self._check(contract, CHECK_INPUT, violations)

    def validate_output(self, capability_id: str, payload) -> LLMAgentCapabilityContractCheck:
        """Check payload against capability_id's current contract's
        output_schema. Never raises for a payload that fails -- every
        mismatch is collected into the returned check's violations.

        Raises:
            UnknownCapabilityError, UnknownContractError: As get()
        """
        contract = self.get(capability_id)
        violations = self._schema_violations(contract, contract.output_schema, payload, CHECK_OUTPUT)
        return self._check(contract, CHECK_OUTPUT, violations)

    def check_requirements(self, capability_id: str, context: dict) -> LLMAgentCapabilityContractCheck:
        """Check context against capability_id's current contract's
        required_context (presence only) and requirements ({field:
        expected} value constraints). Never raises for a context that
        fails -- every missing key and unmet constraint is collected
        into the returned check's violations (Rule: "missing required
        context or requirements must produce structured failures").

        Raises:
            UnknownCapabilityError, UnknownContractError: As get()
            InvalidCapabilityContractError: If context is not a dict
        """
        contract = self.get(capability_id)
        if not isinstance(context, dict):
            raise InvalidCapabilityContractError(
                f"context must be a dict, got {type(context).__name__}"
            )

        violations = []
        for key in contract.required_context:
            if key not in context:
                violations.append(
                    LLMAgentCapabilityContractViolation(
                        capability_id=contract.capability_id,
                        version=contract.version,
                        check=CHECK_REQUIREMENTS,
                        field=key,
                        rule=MISSING_CONTEXT,
                        value=None,
                        message=f"{key!r} is required in context but missing",
                    )
                )

        for field_name, expected in contract.requirements.items():
            if not self._constraint_met(expected, context.get(field_name), field_name in context):
                violations.append(
                    LLMAgentCapabilityContractViolation(
                        capability_id=contract.capability_id,
                        version=contract.version,
                        check=CHECK_REQUIREMENTS,
                        field=field_name,
                        rule=REQUIREMENT_NOT_MET,
                        value=expected,
                        message=(
                            f"{field_name!r} must be {expected!r}, got "
                            f"{context.get(field_name)!r}"
                            if field_name in context
                            else f"{field_name!r} must be {expected!r}, but context does not carry it"
                        ),
                    )
                )

        return self._check(contract, CHECK_REQUIREMENTS, violations)

    @staticmethod
    def _constraint_met(expected, actual, present: bool) -> bool:
        if not present:
            return False
        if isinstance(expected, (list, tuple, set, frozenset)):
            return actual in expected
        return actual == expected

    @staticmethod
    def _check(contract: LLMAgentCapabilityContract, check: str, violations: list) -> LLMAgentCapabilityContractCheck:
        return LLMAgentCapabilityContractCheck(
            capability_id=contract.capability_id,
            version=contract.version,
            check=check,
            valid=not violations,
            violations=violations,
        )

    @staticmethod
    def _schema_violations(contract: LLMAgentCapabilityContract, schema: dict, payload, check: str) -> list:
        """Every way payload fails schema -- the exact
        required/unknown_field/type/enum/minimum/maximum algorithm
        backend.llm.tool_validation.LLMToolValidationService.errors()
        already runs for tool arguments, reused here against an
        arbitrary payload/response dict instead of one tool call's
        arguments."""
        found = []

        def violation(field_name, rule, value, message):
            return LLMAgentCapabilityContractViolation(
                capability_id=contract.capability_id,
                version=contract.version,
                check=check,
                field=field_name,
                rule=rule,
                value=value,
                message=message,
            )

        if not isinstance(payload, dict):
            return [
                violation(
                    None, TYPE, "object", f"payload must be an object, got {type(payload).__name__}"
                )
            ]

        properties = schema["properties"]
        required = schema.get("required", [])

        for field_name in required:
            if field_name not in payload:
                found.append(violation(field_name, REQUIRED, None, f"{field_name!r} is required"))

        if not schema.get("additionalProperties", False):
            for field_name in payload:
                if field_name not in properties:
                    found.append(
                        violation(
                            field_name, UNKNOWN_FIELD, None, f"{field_name!r} is not declared by this contract"
                        )
                    )

        for field_name, spec in properties.items():
            if field_name not in payload:
                continue

            value = payload[field_name]
            declared_type = spec.get("type")

            if declared_type not in _TYPE_CHECKS or not _TYPE_CHECKS[declared_type](value):
                found.append(
                    violation(
                        field_name,
                        TYPE,
                        declared_type,
                        f"{field_name!r} must be of type {declared_type}, got {type(value).__name__}",
                    )
                )
                continue

            if ENUM in spec and value not in spec[ENUM]:
                found.append(
                    violation(
                        field_name, ENUM, spec[ENUM], f"{field_name!r} must be one of {spec[ENUM]!r}, got {value!r}"
                    )
                )

            if declared_type in _NUMERIC_TYPES:
                if MINIMUM in spec and value < spec[MINIMUM]:
                    found.append(
                        violation(
                            field_name, MINIMUM, spec[MINIMUM], f"{field_name!r} must be >= {spec[MINIMUM]}, got {value}"
                        )
                    )
                if MAXIMUM in spec and value > spec[MAXIMUM]:
                    found.append(
                        violation(
                            field_name, MAXIMUM, spec[MAXIMUM], f"{field_name!r} must be <= {spec[MAXIMUM]}, got {value}"
                        )
                    )

        return found

    def _resolve_contract(self, contract) -> LLMAgentCapabilityContract:
        if isinstance(contract, LLMAgentCapabilityContract):
            return contract
        if isinstance(contract, dict):
            return LLMAgentCapabilityContract.from_dict(contract)
        raise InvalidCapabilityContractError(
            f"contract must be an LLMAgentCapabilityContract or dict, got {type(contract).__name__}"
        )
