from backend.agent_capability_contracts import LLMAgentCapabilityContractService, UnknownContractError
from backend.agent_capability_dependencies import LLMAgentCapabilityDependencyService
from backend.agent_capability_resolution import LLMAgentCapabilityResolver

from .models import (
    CHECK_AVAILABILITY,
    CHECK_CONTRACT,
    CHECK_DEPENDENCIES,
    CHECK_EXISTENCE,
    CHECK_REQUIRED_CONTEXT,
    CapabilityCompatibilityResult,
)


class InvalidCapabilityCompatibilityError(ValueError):
    """Raised when check() is given a missing/blank capability_id."""


class LLMAgentCapabilityCompatibility:
    """Determines whether one registered capability can actually operate
    for one agent in one scope/context, by composing every prior commit
    in this series -- never a second validation, permission, or
    dependency-graph engine of its own.

    Every individual check is delegated verbatim to the service that
    already owns it:
      - existence and archived/policy availability: Commit #2's
        LLMAgentCapabilityResolver.resolve() (which itself already
        reuses Commit #1's registry and backend.agent_policy_engine/
        backend.agent_policy_resolution for scope/agent policy) --
        never a second archived check or a second policy evaluation
      - contract presence and required context/configuration: Commit
        #3's LLMAgentCapabilityContractService.get()/check_requirements()
      - dependency satisfiability: Commit #4's
        LLMAgentCapabilityDependencyService.validate_dependencies()

    check() only ever reads through these three collaborators and never
    mutates anything -- no registry, contract, or dependency write
    happens anywhere in this class, and no capability is executed. The
    same (capability_id, agent_id, scope_id, context, and current
    registry/contract/dependency/policy state) always produces the same
    CapabilityCompatibilityResult.

    Ordinary incompatibility (unregistered, unavailable, missing
    contract, unmet requirements, unsatisfiable dependencies) is always
    reported structurally in the returned result, never raised -- the
    same "structured failures, not exceptions, for an ordinary mismatch"
    discipline Commit #3's own validate_input()/validate_output()/
    check_requirements() already keep. Only a malformed call itself
    (a blank capability_id here; a blank agent_id/scope_id or a
    non-dict context, propagated unchanged from
    LLMAgentCapabilityResolver.resolve()) raises.
    """

    def __init__(
        self,
        capability_resolver: LLMAgentCapabilityResolver,
        contract_service: LLMAgentCapabilityContractService,
        dependency_service: LLMAgentCapabilityDependencyService,
    ):
        self._capability_resolver = capability_resolver
        self._contract_service = contract_service
        self._dependency_service = dependency_service

    def check(self, capability_id: str, agent_id: str, scope_id: str, context: dict = None) -> CapabilityCompatibilityResult:
        """Whether capability_id can operate for agent_id in scope_id/context.

        Raises:
            InvalidCapabilityCompatibilityError: If capability_id is
                missing or blank
            InvalidCapabilityResolutionError: Propagated unchanged from
                LLMAgentCapabilityResolver.resolve() if agent_id/scope_id
                is missing/blank, or context is given and is not a dict
        """
        if not capability_id or not isinstance(capability_id, str):
            raise InvalidCapabilityCompatibilityError(
                "capability_id is required and must be a non-empty string"
            )
        if context is None:
            context = {}

        failed_checks = []
        warnings = []
        reasons = []

        resolved = self._capability_resolver.resolve(agent_id, scope_id, context)

        if capability_id not in resolved.resolution_reasons:
            reasons.append(f"capability {capability_id!r} is not registered")
            failed_checks.append(CHECK_EXISTENCE)
            return self._result(capability_id, agent_id, scope_id, failed_checks, warnings, reasons)

        reasons.append(resolved.resolution_reasons[capability_id])
        capability = next(
            candidate
            for candidate in resolved.capabilities + resolved.excluded_capabilities
            if candidate.capability_id == capability_id
        )
        if not any(candidate.capability_id == capability_id for candidate in resolved.capabilities):
            failed_checks.append(CHECK_AVAILABILITY)

        warnings.extend(str(message) for message in capability.metadata.get("warnings", []))

        try:
            contract = self._contract_service.get(capability_id)
        except UnknownContractError as error:
            failed_checks.append(CHECK_CONTRACT)
            reasons.append(f"capability {capability_id!r} has no registered contract: {error}")
        else:
            reasons.append(
                f"capability {capability_id!r} has a registered contract (version {contract.version!r})"
            )
            warnings.extend(str(message) for message in contract.metadata.get("warnings", []))

            requirements_check = self._contract_service.check_requirements(capability_id, context)
            if requirements_check.valid:
                reasons.append(f"capability {capability_id!r} required context/requirements are satisfied")
            else:
                failed_checks.append(CHECK_REQUIRED_CONTEXT)
                reasons.extend(violation.message for violation in requirements_check.violations)

        dependency_result = self._dependency_service.validate_dependencies([capability_id])
        if dependency_result.valid:
            reasons.append(f"capability {capability_id!r} dependencies are satisfied")
        else:
            failed_checks.append(CHECK_DEPENDENCIES)
            if dependency_result.missing_capabilities:
                reasons.append(f"missing dependencies: {dependency_result.missing_capabilities}")
            if dependency_result.cycles:
                reasons.append(f"dependency cycle detected: {dependency_result.cycles}")
            if dependency_result.unresolved_dependencies:
                reasons.append(f"unresolved dependencies: {dependency_result.unresolved_dependencies}")

        return self._result(capability_id, agent_id, scope_id, failed_checks, warnings, reasons)

    @staticmethod
    def _result(capability_id, agent_id, scope_id, failed_checks, warnings, reasons) -> CapabilityCompatibilityResult:
        return CapabilityCompatibilityResult(
            capability_id=capability_id,
            agent_id=agent_id,
            scope_id=scope_id,
            compatible=not failed_checks,
            failed_checks=failed_checks,
            warnings=warnings,
            reasons=reasons,
        )
