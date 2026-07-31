from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_sync_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_sync_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSynchronizationService:
    """
    Keeps consumer projection execution capability registry event
    subscription lifecycle policy profile binding templates —
    including their current definition, published versions, and
    release metadata — synchronized across registries, deployment
    targets, and runtime caches after template updates, publications,
    or releases.

    The service's responsibility is queuing and applying
    synchronization requests, not template creation, membership
    management, version publication, release management, or
    deployment themselves. It does NOT create templates, mutate
    template membership, publish versions, release or retire
    versions, deploy templates, persist synchronization state
    externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Idempotent: Queuing a synchronization for a target that is
      already up to date is a no-op; queuing the same (template,
      target) pair twice while one is already pending is rejected
    - Change-aware: A target is only queued when the template's
      current definition, latest published version, or latest
      released version differs from what was last successfully
      synchronized to it
    - Retriable: A target that fails to synchronize remains eligible
      to be queued and applied again, without disturbing targets that
      already succeeded
    - Immutable-result: Every call returns a new, immutable result; no
      result is ever mutated
    """

    def __init__(
        self,
        template_registry,
        template_version_service,
        release_service,
        target_gateway,
    ):
        """
        Args:
            template_registry: The registry used to resolve a
                template's current definition. Any object exposing
                `find(template_id)`, returning an object with a
                `binding_ids` collection, is accepted
            template_version_service: The service used to resolve a
                template's latest published version. Any object
                exposing `latest(template_id)` is accepted
            release_service: The service used to resolve a template's
                latest released version. Any object exposing
                `latest_release(template_id)` is accepted
            target_gateway: The gateway used to apply a queued
                synchronization to its target. Any object exposing
                `push(template_id, target)`, returning True on success
                and False on failure, is accepted
        """

        for dependency, name in (
            (template_registry, "template registry"),
            (template_version_service, "template version service"),
            (release_service, "release service"),
            (target_gateway, "target gateway"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                    f"Cannot initialize synchronization service with a None {name}."
                )

        self._template_registry = template_registry
        self._template_version_service = template_version_service
        self._release_service = release_service
        self._target_gateway = target_gateway
        self._pending = ()
        self._synchronized_state = {}
        self._known_targets = {}
        self._failed_targets = {}
        self._lock = RLock()

    def sync_target(
        self,
        template_id: str,
        target: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult:
        """
        Queue a synchronization of a template's current state to a
        single target.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError:
                If the template ID or target is None or blank, no
                template is registered under the template ID, or a
                synchronization for the same template and target is
                already pending
        """

        self._validate_identifier(template_id, "template ID")
        self._validate_identifier(target, "target")

        with self._lock:
            template = self._resolve_template(template_id)

            if any(
                pending.template_id == template_id and pending.target == target
                for pending in self._pending
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                    f"A synchronization for template ID {template_id!r} and target {target!r} is already pending."
                )

            if self._is_up_to_date(template_id, target, template):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncRequest(
                template_id=template_id,
                operation="register",
                target=target,
            )

            self._pending = self._pending + (request,)
            self._known_targets.setdefault(template_id, set()).add(target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult(
                synchronized=True,
                synchronized_targets=(target,),
                failed_targets=(),
            )

    def sync(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult:
        """
        Queue a synchronization of a template's current state to
        every target it has previously been associated with,
        including any that are currently pending retry after a prior
        failure.

        Templates that have never been associated with a target have
        nothing to synchronize, so calling this is a no-op for them.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError:
                If the template ID is None or blank, or no template is
                registered under it
        """

        self._validate_identifier(template_id, "template ID")

        with self._lock:
            self._resolve_template(template_id)

            targets = set(self._known_targets.get(template_id, set())) | set(
                self._failed_targets.get(template_id, set())
            )

        synchronized_targets = []

        for target in sorted(targets):
            result = self.sync_target(template_id, target)
            synchronized_targets.extend(result.synchronized_targets)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult(
            synchronized=bool(synchronized_targets),
            synchronized_targets=tuple(synchronized_targets),
            failed_targets=(),
        )

    def sync_all(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult:
        """
        Apply every pending synchronization request.

        A target whose synchronization fails is recorded as failed
        and remains eligible to be queued and applied again; it does
        not block other targets from being applied.

        Returns:
            An immutable result carrying every target that was
            successfully synchronized and every target that failed,
            in the order the requests were queued
        """

        with self._lock:
            if not self._pending:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            pending_requests = self._pending
            self._pending = ()

            synchronized_targets = []
            failed_targets = []

            for request in pending_requests:
                if self._target_gateway.push(request.template_id, request.target):
                    template = self._template_registry.find(request.template_id)

                    self._synchronized_state[(request.template_id, request.target)] = self._snapshot(
                        request.template_id, template
                    )
                    self._failed_targets.get(request.template_id, set()).discard(request.target)

                    synchronized_targets.append(request.target)
                else:
                    self._failed_targets.setdefault(request.template_id, set()).add(request.target)

                    failed_targets.append(request.target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncResult(
                synchronized=bool(synchronized_targets),
                synchronized_targets=tuple(synchronized_targets),
                failed_targets=tuple(failed_targets),
            )

    def pending(self) -> tuple:
        """
        List every synchronization request queued but not yet
        applied, preserving the order they were queued.
        """

        with self._lock:
            return self._pending

    def is_synchronized(self, template_id: str) -> bool:
        """
        Check whether a template is fully synchronized: it has at
        least one target it has been synchronized to, and no target
        is currently pending or failed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError:
                If the template ID is None or blank
        """

        self._validate_identifier(template_id, "template ID")

        with self._lock:
            if self._failed_targets.get(template_id):
                return False

            if any(pending.template_id == template_id for pending in self._pending):
                return False

            return bool(self._known_targets.get(template_id))

    def _is_up_to_date(self, template_id: str, target: str, template) -> bool:
        return self._synchronized_state.get((template_id, target)) == self._snapshot(template_id, template)

    def _snapshot(self, template_id: str, template) -> tuple:
        try:
            version_id = self._template_version_service.latest(template_id).version
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError:
            version_id = None

        latest_release = self._release_service.latest_release(template_id)
        released_version = latest_release.version if latest_release is not None else None

        return (tuple(template.binding_ids), version_id, released_version)

    def _resolve_template(self, template_id: str):
        template = self._template_registry.find(template_id)

        if template is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                f"Cannot synchronize: no template is registered under template ID {template_id!r}."
            )

        return template

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                f"Cannot synchronize with an empty or blank {label}."
            )
