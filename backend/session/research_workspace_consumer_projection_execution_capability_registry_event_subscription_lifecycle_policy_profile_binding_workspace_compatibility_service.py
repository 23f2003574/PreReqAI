from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_compatibility_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity,
)


def _non_empty_resources(bindings, templates, presets, groups) -> bool:
    return len(bindings) + len(templates) + len(presets) + len(groups) > 0


def _no_overlapping_bindings(bindings, templates, presets, groups) -> bool:
    direct_ids = {binding.binding_id for binding in bindings}

    indirect_ids = set()

    for template in templates:
        indirect_ids.update(template.binding_ids)

    for group in groups:
        indirect_ids.update(group.binding_ids)

    return direct_ids.isdisjoint(indirect_ids)


def _no_overlapping_templates(bindings, templates, presets, groups) -> bool:
    direct_ids = {template.template_id for template in templates}

    indirect_ids = set()

    for preset in presets:
        indirect_ids.update(preset.binding_template_ids)

    return direct_ids.isdisjoint(indirect_ids)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityService:
    """
    Checks whether every binding, binding template, binding preset,
    and binding group referenced by a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace is mutually compatible, by evaluating a fixed
    set of named compatibility rules before a workspace is published
    or deployed.

    The service's responsibility is compatibility evaluation, not
    workspace creation, registration, resolution, or persistence. It
    does NOT create workspaces, register resources, mutate a
    registry, persist results, log, or publish events.

    The service is:
    - Stateless: Holds only the fixed rules and lookup sources it was
      constructed with
    - Deterministic: Same workspace and resolved resources always
      produce the same outcome, evaluated in a fixed, declared order
    - Side-effect free: Never mutates its inputs or the registries it
      checks against
    """

    _RULE_EVALUATORS = {
        "non_empty_resources": _non_empty_resources,
        "no_overlapping_bindings": _no_overlapping_bindings,
        "no_overlapping_templates": _no_overlapping_templates,
    }

    DEFAULT_RULES = (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule(
            rule_id="non_empty_resources",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule(
            rule_id="no_overlapping_bindings",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity.ERROR,
        ),
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule(
            rule_id="no_overlapping_templates",
            severity=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity.WARNING,
        ),
    )

    def __init__(
        self,
        workspace_resolver,
        binding_registry,
        template_registry,
        preset_registry,
        group_registry,
        rules=None,
    ):
        """
        Args:
            workspace_resolver: The resolver used to resolve a
                workspace and its eligible member resources for a
                workspace ID. Any object exposing `resolve(workspace_id)`
                and `resolve_resources(workspace_id)` is accepted
            binding_registry: The registry used to resolve a raw
                workspace's member bindings by ID. Any object
                exposing `find(binding_id)` is accepted
            template_registry: The registry used to resolve a raw
                workspace's member binding templates by ID. Any
                object exposing `find(template_id)` is accepted
            preset_registry: The registry used to resolve a raw
                workspace's member binding presets by ID. Any object
                exposing `find(preset_id)` is accepted
            group_registry: The registry used to resolve a raw
                workspace's member binding groups by ID. Any object
                exposing `find(group_id)` is accepted
            rules: The compatibility rules to evaluate, or None to use
                the service's default rules

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError:
                If any rule is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule,
                has a blank or unrecognized rule ID, an invalid
                severity, or two rules share the same rule ID
        """

        self._workspace_resolver = workspace_resolver
        self._binding_registry = binding_registry
        self._template_registry = template_registry
        self._preset_registry = preset_registry
        self._group_registry = group_registry
        self._rules = self._validated_rules(rules if rules is not None else self.DEFAULT_RULES)

    def check(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityResult:
        """
        Evaluate every configured compatibility rule for a
        workspace's eligible member resources.

        Returns:
            An immutable compatibility result carrying every rule
            that failed and whether the workspace is overall
            compatible

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError:
                If the workspace ID is None or blank, or no workspace
                is registered under it
        """

        self._validate_identifier(workspace_id, "workspace ID")

        result = self._workspace_resolver.resolve(workspace_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                f"Cannot check compatibility: no workspace is registered under workspace ID {workspace_id!r}."
            )

        resources = self._workspace_resolver.resolve_resources(workspace_id)

        return self._evaluate(
            resources["bindings"],
            resources["templates"],
            resources["presets"],
            resources["groups"],
        )

    def supports(self, workspace_id: str) -> bool:
        """
        Check whether a workspace's eligible member resources are
        mutually compatible.

        Returns:
            True if every ERROR-severity compatibility rule passed,
            False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError:
                If the workspace ID is None or blank, or no workspace
                is registered under it
        """

        return self.check(workspace_id).compatible

    def validate(self, workspace) -> None:
        """
        Validate that a workspace's referenced resources are
        compatible, raising if they are not.

        Member resources that are unknown to the configured
        registries are skipped rather than treated as a failure.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError:
                If the workspace is None, its workspace ID is None or
                blank, or the workspace fails a required
                compatibility rule
        """

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                "Cannot validate a None workspace."
            )

        workspace_id = getattr(workspace, "workspace_id", None)

        self._validate_identifier(workspace_id, "workspace ID")

        bindings = self._resolve_members(workspace.binding_ids, self._binding_registry)
        templates = self._resolve_members(workspace.template_ids, self._template_registry)
        presets = self._resolve_members(workspace.preset_ids, self._preset_registry)
        groups = self._resolve_members(workspace.group_ids, self._group_registry)

        result = self._evaluate(bindings, templates, presets, groups)

        if not result.compatible:
            rule_ids = ", ".join(violation.rule_id for violation in result.violations)

            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                f"Workspace failed required compatibility rules: {rule_ids}."
            )

    def rules(self) -> tuple:
        """
        List every configured compatibility rule, in evaluation
        order.
        """

        return self._rules

    def _resolve_members(self, member_ids, registry) -> tuple:
        return tuple(
            member
            for member in (registry.find(member_id) for member_id in member_ids)
            if member is not None
        )

    def _evaluate(
        self,
        bindings,
        templates,
        presets,
        groups,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityResult:
        violations = []
        compatible = True

        for rule in self._rules:
            evaluator = self._RULE_EVALUATORS[rule.rule_id]

            if not evaluator(bindings, templates, presets, groups):
                violations.append(rule)

                if rule.severity == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity.ERROR:
                    compatible = False

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityResult(
            compatible=compatible,
            violations=tuple(violations),
        )

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                f"Cannot check compatibility with an empty or blank {label}."
            )

    def _validated_rules(self, rules) -> tuple:
        seen_ids = set()
        validated = []

        for rule in rules:
            if rule is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                    "Cannot build a compatibility service with a None rule."
                )

            if not isinstance(
                rule,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                    "Cannot build a compatibility service: rule must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule."
                )

            if rule.rule_id is None or not rule.rule_id.strip() or rule.rule_id not in self._RULE_EVALUATORS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                    f"Cannot build a compatibility service with an invalid compatibility rule ID {rule.rule_id!r}."
                )

            if not isinstance(
                rule.severity,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                    f"Cannot build a compatibility service with a rule that has an unknown severity {rule.severity!r}."
                )

            if rule.rule_id in seen_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityError(
                    f"Cannot build a compatibility service with duplicate rule ID {rule.rule_id!r}."
                )

            seen_ids.add(rule.rule_id)
            validated.append(rule)

        return tuple(validated)
