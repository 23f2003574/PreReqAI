"""Tests for LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator
and its integration into #6's AgentTaskRecoveryExecutionDecisionLifecycleHealthResult.

Reuses backend.cli._build_collaborators() (#8) for a fully, correctly
wired real configuration -- the same wiring this package's own
production entrypoints (CLI, API) already use -- instead of re-deriving
service construction a second time.
"""

import backend.agent_task_recovery_execution_precondition_snapshots.decision_lifecycle_configuration_validation as cv

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CONFIGURATION_INVALID,
    CONFIGURATION_VALID,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService,
)

from backend.cli import _build_collaborators

from backend.tests.test_llm_agent_task_recovery_execution_decision_impact_invalidation_lifecycle_reconciliation import (
    TASK_ID,
    _Recon,
)


def _wired_kwargs():
    c = _build_collaborators()
    return dict(
        decision_store=c.decision_store, resolution_service=c.resolution,
        supersession_validation_service=c.supersession_validation, impact_service=c.impact,
        staleness_service=c.staleness, lifecycle_result_service=c.lifecycle_results,
        lifecycle_verification_service=c.lifecycle_verification, lifecycle_service=c.lifecycle,
        reconciliation_service=c.reconciliation,
    )


def test_valid_configuration_reports_no_issues():
    validator = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**_wired_kwargs())

    result = validator.validate()

    assert result.status == CONFIGURATION_VALID
    assert result.valid is True
    assert result.issues == ()
    assert result.missing_dependencies == ()
    assert result.unsupported_configuration == ()


def test_missing_dependency_is_reported_and_invalid():
    kwargs = _wired_kwargs()
    kwargs["staleness_service"] = None

    result = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**kwargs).validate()

    assert result.status == CONFIGURATION_INVALID
    assert "staleness_service" in result.missing_dependencies


def test_invalid_value_is_reported_when_a_collaborator_lacks_the_required_capability():
    kwargs = _wired_kwargs()
    kwargs["resolution_service"] = object()  # present, but exposes no resolve()

    result = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**kwargs).validate()

    assert result.status == CONFIGURATION_INVALID
    assert any("resolution_service" in issue and "resolve" in issue for issue in result.issues)


def test_incompatible_settings_are_reported_as_unsupported_configuration():
    """reconciliation_service configured without lifecycle_service is an
    incompatible combination: reconciliation cannot run a replacement
    lifecycle without one."""
    kwargs = _wired_kwargs()
    kwargs["lifecycle_service"] = None

    result = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**kwargs).validate()

    assert result.status == CONFIGURATION_INVALID
    assert "lifecycle_service" in result.missing_dependencies
    assert any("reconciliation_service" in issue for issue in result.unsupported_configuration)


def test_unsupported_schema_version_is_reported(monkeypatch):
    monkeypatch.setattr(cv, "LIFECYCLE_RESULT_SCHEMA_VERSION", 99)
    validator = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**_wired_kwargs())

    result = validator.validate()

    assert result.status == CONFIGURATION_INVALID
    assert any("schema version 99" in item for item in result.unsupported_configuration)


def test_missing_environment_capability_is_reported(monkeypatch):
    monkeypatch.setattr(
        cv, "_ENVIRONMENT_CAPABILITIES",
        (("fake_capability", "backend.totally_not_a_real_module", "NotARealClass"),),
    )
    validator = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**_wired_kwargs())

    result = validator.validate()

    assert result.status == CONFIGURATION_INVALID
    assert any("fake_capability" in item for item in result.missing_dependencies)


def test_multiple_simultaneous_issues_are_all_reported_independently():
    kwargs = _wired_kwargs()
    kwargs["staleness_service"] = None
    kwargs["lifecycle_service"] = None

    result = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**kwargs).validate()

    assert result.status == CONFIGURATION_INVALID
    assert "staleness_service" in result.missing_dependencies
    assert "lifecycle_service" in result.missing_dependencies
    assert result.unsupported_configuration != ()


def test_validate_is_deterministic_and_never_mutates_anything():
    kwargs = _wired_kwargs()
    validator = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**kwargs)
    history_before = kwargs["lifecycle_result_service"].history(TASK_ID)

    first = validator.validate()
    second = validator.validate()

    assert first == second
    assert kwargs["lifecycle_result_service"].history(TASK_ID) == history_before


def test_inconsistent_decision_store_wiring_is_flagged():
    """Two different decision_store instances wired into the same
    lifecycle is a real, silent-data-loss misconfiguration -- must be
    caught even though every individual collaborator looks fine alone."""
    from backend.agent_task_recovery_execution_precondition_snapshots import (
        LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
        LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
    )

    kwargs = _wired_kwargs()
    other_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    kwargs["resolution_service"] = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
        decision_store=other_store,
    )

    result = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(**kwargs).validate()

    assert result.status == CONFIGURATION_INVALID
    assert any("resolution_service" in issue and "different decision_store" in issue for issue in result.issues)


def test_health_result_from_6_carries_the_configuration_validation():
    recon = _Recon(resolution_chain=("d1",))
    recon.results.record(TASK_ID, recon.lifecycle.run(TASK_ID))
    from types import SimpleNamespace
    from backend.agent_task_recovery_execution_precondition_snapshots import SUPERSESSION_VALID

    service = LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService(
        decision_store=recon.f.decision_store,
        resolution_service=recon.resolution,
        supersession_validation_service=SimpleNamespace(
            validate=lambda task_id: SimpleNamespace(status=SUPERSESSION_VALID, issues=(), chain=(), terminal_decision_id=None),
        ),
        impact_service=recon.f.impact,
        staleness_service=recon.f.staleness,
        lifecycle_result_service=recon.results,
        lifecycle_verification_service=recon.verifier,
    )

    result = service.check(TASK_ID)

    # The health service's own default configuration_validator only has
    # the seven collaborators it itself holds -- lifecycle_service and
    # reconciliation_service are legitimately absent from it (a caller
    # with the full nine-collaborator wiring, e.g. backend/cli.py's
    # build_recovery_decision_health_service(), passes its own complete
    # validator instead). Integration is what's being proven here: the
    # health result carries a real, populated validation outcome.
    assert result.configuration_validation is not None
    assert result.configuration_validation.status == CONFIGURATION_INVALID
    assert set(result.configuration_validation.missing_dependencies) == {"lifecycle_service", "reconciliation_service"}
    assert result.to_dict()["configuration_validation"]["missing_dependencies"] == [
        "lifecycle_service", "reconciliation_service",
    ]


def test_health_service_reports_valid_when_given_the_full_nine_collaborator_validator():
    """The production path (backend/cli.py's build_recovery_decision_
    health_service(), #8) supplies a configuration_validator built from
    all nine collaborators -- confirming that path reports VALID."""
    c = _build_collaborators()
    configuration_validator = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(
        decision_store=c.decision_store, resolution_service=c.resolution,
        supersession_validation_service=c.supersession_validation, impact_service=c.impact,
        staleness_service=c.staleness, lifecycle_result_service=c.lifecycle_results,
        lifecycle_verification_service=c.lifecycle_verification, lifecycle_service=c.lifecycle,
        reconciliation_service=c.reconciliation,
    )
    service = LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService(
        decision_store=c.decision_store, resolution_service=c.resolution,
        supersession_validation_service=c.supersession_validation, impact_service=c.impact,
        staleness_service=c.staleness, lifecycle_result_service=c.lifecycle_results,
        lifecycle_verification_service=c.lifecycle_verification,
        configuration_validator=configuration_validator,
    )

    result = service.check("never-seen-task")

    assert result.configuration_validation.status == CONFIGURATION_VALID
