from backend.agent_capability_contracts import LLMAgentCapabilityContractService, UnknownContractError
from backend.agent_capability_registry import UnknownCapabilityError
from backend.llm.secret_redaction import LLMSecretRedactionService

from .models import ExecutionValidationResult

_redactor = LLMSecretRedactionService()


class InvalidExecutionValidationError(ValueError):
    """Raised when validate_start()/validate_result() is given a
    missing/blank capability_id or version, or (validate_start only) a
    context that is not a dict."""


class LLMAgentCapabilityExecutionValidator:
    """Validates a capability execution's input/context before it starts,
    and its output once it finishes, against the exact
    LLMAgentCapabilityContract version being executed -- never a second
    schema engine, never an execution engine.

    Every actual check is delegated to Commit #3's own
    LLMAgentCapabilityContractService: validate_input()/validate_output()
    for schema conformance and check_requirements() for required_context/
    requirements, all three now accepting an explicit version argument
    (an additive, backward-compatible Commit #3 extension made for this
    commit -- version=None, every existing caller's default, keeps
    resolving to the capability's current registry version exactly as
    before) so this validator can always check against the *exact*
    version an execution recorded, never whatever a capability's current
    version happens to be by the time validation runs (Rule: "validate
    against the exact capability version being executed").

    Security scanning reuses backend.llm.secret_redaction.
    LLMSecretRedactionService.detect() -- the repository's own canonical
    secret-detection utility (Rule: "reuse existing redaction/security
    validation where applicable") -- to flag a payload/context that looks
    like it carries a raw credential. This is advisory (a warning, never
    an error): a schema-valid payload that happens to contain something
    secret-shaped is still schema-valid, so it can never fail validation
    on its own, but a caller is still told about it. backend.llm.
    input_security/output_security were considered and not reused here:
    both operate on LLMRequest/LLMResponse specifically (prompt-injection
    and jailbreak pattern matching over LLM conversation text), an
    unrelated shape this module would have to fabricate fake
    conversation objects to call -- LLMSecretRedactionService.detect()
    already works directly on an arbitrary payload/context value, which
    is exactly what an execution's input/output/context actually are.

    Both methods only ever read (LLMAgentCapabilityContractService.
    validate_input()/validate_output()/check_requirements(), all
    themselves read-only) -- no capability, contract, or execution
    record is ever created, changed, or removed, and no capability is
    executed, retried, or altered here (Rule: "this validates; it does
    not execute, retry, or alter execution records" -- this module has
    no dependency on Commit #7's LLMAgentCapabilityExecutionService at
    all).
    """

    def __init__(self, contract_service: LLMAgentCapabilityContractService):
        self._contract_service = contract_service

    def validate_start(
        self, capability_id: str, version: str, input_payload, context: dict
    ) -> ExecutionValidationResult:
        """Validate input_payload/context against capability_id's exact
        version contract, before an execution is started.

        Raises:
            InvalidExecutionValidationError: If capability_id or version
                is missing or blank, or context is not a dict
        """
        self._validate_id(capability_id, "capability_id")
        self._validate_id(version, "version")
        if not isinstance(context, dict):
            raise InvalidExecutionValidationError(
                f"context must be a dict, got {type(context).__name__}"
            )

        try:
            input_check = self._contract_service.validate_input(capability_id, input_payload, version=version)
            requirements_check = self._contract_service.check_requirements(capability_id, context, version=version)
        except (UnknownCapabilityError, UnknownContractError) as error:
            return ExecutionValidationResult(
                valid=False,
                errors=[f"cannot validate capability {capability_id!r} version {version!r}: {error}"],
                warnings=[],
            )

        errors = [violation.message for violation in input_check.violations]
        errors.extend(violation.message for violation in requirements_check.violations)

        warnings = self._security_warnings(input_payload, "input_payload")
        warnings.extend(self._security_warnings(context, "context"))

        return ExecutionValidationResult(valid=not errors, errors=errors, warnings=warnings)

    def validate_result(self, capability_id: str, version: str, output_payload) -> ExecutionValidationResult:
        """Validate output_payload against capability_id's exact version
        contract, after an execution has finished.

        Raises:
            InvalidExecutionValidationError: If capability_id or version
                is missing or blank
        """
        self._validate_id(capability_id, "capability_id")
        self._validate_id(version, "version")

        try:
            output_check = self._contract_service.validate_output(capability_id, output_payload, version=version)
        except (UnknownCapabilityError, UnknownContractError) as error:
            return ExecutionValidationResult(
                valid=False,
                errors=[f"cannot validate capability {capability_id!r} version {version!r}: {error}"],
                warnings=[],
            )

        errors = [violation.message for violation in output_check.violations]
        warnings = self._security_warnings(output_payload, "output_payload")

        return ExecutionValidationResult(valid=not errors, errors=errors, warnings=warnings)

    @staticmethod
    def _security_warnings(value, label: str) -> list:
        return [
            f"{label} may contain a {finding['pattern']} at {finding['location']}"
            for finding in _redactor.detect(value)
        ]

    @staticmethod
    def _validate_id(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidExecutionValidationError(
                f"{field_name} is required and must be a non-empty string"
            )
