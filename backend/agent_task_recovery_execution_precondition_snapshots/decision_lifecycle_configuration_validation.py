from dataclasses import dataclass

from .models import HEALTH_RESULT_SCHEMA_VERSION, LIFECYCLE_RESULT_SCHEMA_VERSION

CONFIGURATION_VALID = "valid"
CONFIGURATION_INVALID = "invalid"

# The nine collaborators the facade (#1)/health service (#6)/dependency
# diagnostics (#7) chain composes between them -- the full lifecycle
# dependency graph this validator checks the wiring of. name -> the
# capability (duck-typed attribute) a real implementation must expose,
# the same "duck-typed to what each already exposes" discipline
# backend.session.ExecutionRuntimeHealthService's own collaborators
# already follow, so a test double only needs to expose what it's
# actually used for, never a specific concrete class.
_REQUIRED_COLLABORATORS = (
    ("decision_store", "history"),
    ("resolution_service", "resolve"),
    ("supersession_validation_service", "validate"),
    ("impact_service", "analyze"),
    ("staleness_service", "check"),
    ("lifecycle_result_service", "latest"),
    ("lifecycle_verification_service", "verify"),
    ("lifecycle_service", "run"),
    ("reconciliation_service", "reconcile"),
)

# The real, already-implemented external mechanisms this package's
# execution/invalidation services integrate with (decision_impact_
# invalidation.py's own mechanism dict) -- "required environment-
# dependent capabilities": whether the sibling packages providing them
# are even importable in this environment, never whether a particular
# facade/health instance happens to have them wired (that's optional --
# see build_recovery_decision_facade()'s own docstring in backend/cli.py).
_ENVIRONMENT_CAPABILITIES = (
    ("precondition_revalidation", "backend.agent_task_recovery_execution_precondition_snapshots.revalidation", "LLMAgentTaskRecoveryExecutionPreconditionRevalidationService"),
    ("preflight_invalidation", "backend.agent_task_recovery_guardrails.preflight_invalidation", "LLMAgentTaskRecoveryPreflightInvalidationService"),
    ("retry_scheduling", "backend.agent_task_queue_retry_scheduler.service", "LLMAgentTaskRetryScheduler"),
)


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidationResult:
    """LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator.validate()'s
    outcome. status is CONFIGURATION_VALID only when issues,
    missing_dependencies, and unsupported_configuration are all empty --
    never a second, independently-set flag that could drift from them."""

    status: str
    issues: tuple
    missing_dependencies: tuple
    unsupported_configuration: tuple

    @property
    def valid(self) -> bool:
        return self.status == CONFIGURATION_VALID

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": list(self.issues),
            "missing_dependencies": list(self.missing_dependencies),
            "unsupported_configuration": list(self.unsupported_configuration),
        }


class LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator:
    """Validates the recovery execution decision lifecycle's own
    configuration and dependency wiring -- never a new configuration
    system or DI container (this repository has neither: no settings
    module, no env-var reads, no container framework exist anywhere in
    it; this validator checks the plain constructor wiring
    backend/cli.py's build_recovery_decision_facade()/
    build_recovery_decision_health_service() already produce, the only
    "configuration" this lifecycle actually has).

    validate() takes no task_id and performs no task-data reads: it is
    static, deterministic wiring/capability validation, never recovery
    execution, never task mutation, and (import checks aside) no network
    calls beyond what already happens at process startup.
    """

    def __init__(
        self,
        decision_store=None,
        resolution_service=None,
        supersession_validation_service=None,
        impact_service=None,
        staleness_service=None,
        lifecycle_result_service=None,
        lifecycle_verification_service=None,
        lifecycle_service=None,
        reconciliation_service=None,
    ):
        self._collaborators = {
            "decision_store": decision_store,
            "resolution_service": resolution_service,
            "supersession_validation_service": supersession_validation_service,
            "impact_service": impact_service,
            "staleness_service": staleness_service,
            "lifecycle_result_service": lifecycle_result_service,
            "lifecycle_verification_service": lifecycle_verification_service,
            "lifecycle_service": lifecycle_service,
            "reconciliation_service": reconciliation_service,
        }

    def validate(self) -> AgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidationResult:
        issues, missing, unsupported = [], [], []

        for name, required_attribute in _REQUIRED_COLLABORATORS:
            collaborator = self._collaborators[name]
            if collaborator is None:
                missing.append(name)
            elif not hasattr(collaborator, required_attribute):
                issues.append(f"{name} does not expose {required_attribute}() -- invalid configuration")

        self._check_shared_decision_store(issues)

        if LIFECYCLE_RESULT_SCHEMA_VERSION != 1:
            unsupported.append(f"unsupported AgentTaskRecoveryExecutionDecisionLifecycleResult schema version {LIFECYCLE_RESULT_SCHEMA_VERSION!r}")
        if HEALTH_RESULT_SCHEMA_VERSION != 1:
            unsupported.append(f"unsupported AgentTaskRecoveryExecutionDecisionLifecycleHealthResult schema version {HEALTH_RESULT_SCHEMA_VERSION!r}")

        for capability_name, module_name, class_name in _ENVIRONMENT_CAPABILITIES:
            try:
                module = __import__(module_name, fromlist=[class_name])
                getattr(module, class_name)
            except (ImportError, AttributeError) as error:
                missing.append(f"environment capability {capability_name} unavailable: {type(error).__name__}: {error}")

        if self._collaborators["reconciliation_service"] is not None and (
            self._collaborators["lifecycle_service"] is None or self._collaborators["lifecycle_result_service"] is None
        ):
            unsupported.append(
                "reconciliation_service is configured without both lifecycle_service and "
                "lifecycle_result_service -- reconciliation cannot run a replacement lifecycle or persist it"
            )

        status = (
            CONFIGURATION_VALID if not issues and not missing and not unsupported else CONFIGURATION_INVALID
        )
        return AgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidationResult(
            status=status, issues=tuple(issues), missing_dependencies=tuple(missing),
            unsupported_configuration=tuple(unsupported),
        )

    def _check_shared_decision_store(self, issues):
        """Lifecycle dependency wiring: every collaborator that reads
        decisions must share the exact same decision_store instance the
        rest of the lifecycle was configured with -- two different
        stores wired in by mistake is a real, silent-data-loss class of
        misconfiguration (decisions saved through one are invisible to
        the other), never detectable from any one collaborator alone."""
        decision_store = self._collaborators["decision_store"]
        if decision_store is None:
            return
        for name in ("resolution_service", "supersession_validation_service", "impact_service"):
            collaborator = self._collaborators[name]
            other_store = getattr(collaborator, "_decision_store", None)
            if other_store is not None and other_store is not decision_store:
                issues.append(f"{name} is wired to a different decision_store than the configured one")
