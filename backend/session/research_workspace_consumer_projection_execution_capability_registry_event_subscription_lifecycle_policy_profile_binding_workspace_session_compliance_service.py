from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_compliance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_compliance_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceService:
    """
    Evaluates a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution session against a set of reusable, independently
    enable-able compliance rules, so a session can be blocked from
    executing when it violates a rule serious enough to matter.

    The service's responsibility is evaluation and reporting, not
    defining what makes a rule violated. It relies on a
    violation_checker, given at construction time, to decide whether
    a specific rule is violated by a specific session.

    Behavior:
    - Only currently enabled rules are ever evaluated; a disabled
      rule is skipped entirely, even if it would otherwise be
      violated
    - A "CRITICAL" violation blocks the session: evaluate() raises
      after recording the result. A "WARNING" violation is recorded
      but does not block
    - Every evaluate() call replaces the previously retained result
      for that session, whether or not it raised
    - report() reads back the most recently retained result without
      re-evaluating anything

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, rules=(), violation_checker=None):
        """
        Args:
            rules: The
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceRule
                instances to register upfront, keyed by their rule_id
            violation_checker: A callable(rule, session_id) -> bool
                deciding whether a specific rule is violated by a
                specific session. Defaults to a checker that reports
                no violations for any rule or session

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError:
                If two given rules share a rule_id
        """

        self._rules_by_id = {}
        self._violation_checker = violation_checker or (lambda rule, session_id: False)
        self._results_by_session_id = {}
        self._lock = RLock()

        for rule in rules:
            if rule.rule_id in self._rules_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                    f"Rule ID {rule.rule_id!r} is already registered."
                )

            self._rules_by_id[rule.rule_id] = rule

    def evaluate(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceResult:
        """
        Evaluate every currently enabled rule against a session,
        immediately before it executes.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError:
                If session_id is None or blank, or the session
                violates a rule with "CRITICAL" severity
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            enabled_rules = [rule for rule in self._rules_by_id.values() if rule.enabled]
            violated_rules = [rule for rule in enabled_rules if self._violation_checker(rule, session_id)]
            violated_ids = tuple(sorted(rule.rule_id for rule in violated_rules))

            result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceResult(
                compliant=not violated_ids,
                violations=violated_ids,
            )

            self._results_by_session_id[session_id] = result

            critical_violations = tuple(
                sorted(rule.rule_id for rule in violated_rules if rule.severity == "CRITICAL")
            )

            if critical_violations:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                    f"Session ID {session_id!r} blocked by critical compliance violation(s): "
                    f"{critical_violations!r}."
                )

            return result

    def enable(self, rule_id: str) -> None:
        """
        Enable a registered rule, so it is evaluated the next time
        evaluate() runs.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError:
                If rule_id is None or blank, or no rule is registered
                under it
        """

        self._validate_id(rule_id, "rule ID")

        with self._lock:
            rule = self._resolve_rule(rule_id)

            self._rules_by_id[rule_id] = replace(rule, enabled=True)

    def disable(self, rule_id: str) -> None:
        """
        Disable a registered rule, so it is skipped the next time
        evaluate() runs.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError:
                If rule_id is None or blank, or no rule is registered
                under it
        """

        self._validate_id(rule_id, "rule ID")

        with self._lock:
            rule = self._resolve_rule(rule_id)

            self._rules_by_id[rule_id] = replace(rule, enabled=False)

    def active_rules(self) -> tuple:
        """
        List every currently enabled rule.
        """

        with self._lock:
            return tuple(rule for rule in self._rules_by_id.values() if rule.enabled)

    def report(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceResult:
        """
        Read back the most recently retained evaluation result for a
        session, without re-evaluating anything.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError:
                If session_id is None or blank, or the session has
                never been evaluated
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            result = self._results_by_session_id.get(session_id)

            if result is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                    f"Session ID {session_id!r} has never been evaluated."
                )

            return result

    def _resolve_rule(
        self, rule_id: str
    ):
        rule = self._rules_by_id.get(rule_id)

        if rule is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                f"No compliance rule is registered under rule ID {rule_id!r}."
            )

        return rule

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                f"Cannot operate with an empty or blank {label}."
            )
