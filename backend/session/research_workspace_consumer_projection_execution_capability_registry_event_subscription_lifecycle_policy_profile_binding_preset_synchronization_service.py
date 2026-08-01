from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_sync_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_sync_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSynchronizationService:
    """
    Keeps consumer projection execution capability registry event
    subscription lifecycle policy profile binding presets —
    including their current definition, published versions, and
    release metadata — synchronized across registries, deployment
    targets, and runtime caches after preset updates, publications,
    or releases.

    The service's responsibility is queuing and applying
    synchronization requests, not preset creation, membership
    management, version publication, release management, or
    deployment themselves. It does NOT create presets, mutate preset
    membership, publish versions, release or retire versions, deploy
    presets, persist synchronization state externally, log, or
    publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Idempotent: Queuing a synchronization for a target that is
      already up to date is a no-op; queuing the same (preset,
      target) pair twice while one is already pending is rejected
    - Change-aware: A target is only queued when the preset's current
      definition, latest published version, or latest released
      version differs from what was last successfully synchronized
      to it
    - Retriable: A target that fails to synchronize remains eligible
      to be queued and applied again, without disturbing targets that
      already succeeded
    - Immutable-result: Every call returns a new, immutable result; no
      result is ever mutated
    """

    def __init__(
        self,
        preset_registry,
        preset_version_service,
        release_service,
        target_gateway,
    ):
        """
        Args:
            preset_registry: The registry used to resolve a preset's
                current definition. Any object exposing
                `find(preset_id)`, returning an object with a
                `binding_template_ids` collection, is accepted
            preset_version_service: The service used to resolve a
                preset's latest published version. Any object
                exposing `latest(preset_id)` is accepted
            release_service: The service used to resolve a preset's
                latest released version. Any object exposing
                `latest_release(preset_id)` is accepted
            target_gateway: The gateway used to apply a queued
                synchronization to its target. Any object exposing
                `push(preset_id, target)`, returning True on success
                and False on failure, is accepted
        """

        for dependency, name in (
            (preset_registry, "preset registry"),
            (preset_version_service, "preset version service"),
            (release_service, "release service"),
            (target_gateway, "target gateway"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError(
                    f"Cannot initialize synchronization service with a None {name}."
                )

        self._preset_registry = preset_registry
        self._preset_version_service = preset_version_service
        self._release_service = release_service
        self._target_gateway = target_gateway
        self._pending = ()
        self._synchronized_state = {}
        self._known_targets = {}
        self._failed_targets = {}
        self._lock = RLock()

    def sync_target(
        self,
        preset_id: str,
        target: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult:
        """
        Queue a synchronization of a preset's current state to a
        single target.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError:
                If the preset ID or target is None or blank, no
                preset is registered under the preset ID, or a
                synchronization for the same preset and target is
                already pending
        """

        self._validate_identifier(preset_id, "preset ID")
        self._validate_identifier(target, "target")

        with self._lock:
            preset = self._resolve_preset(preset_id)

            if any(
                pending.preset_id == preset_id and pending.target == target
                for pending in self._pending
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError(
                    f"A synchronization for preset ID {preset_id!r} and target {target!r} is already pending."
                )

            if self._is_up_to_date(preset_id, target, preset):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncRequest(
                preset_id=preset_id,
                operation="register",
                target=target,
            )

            self._pending = self._pending + (request,)
            self._known_targets.setdefault(preset_id, set()).add(target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult(
                synchronized=True,
                synchronized_targets=(target,),
                failed_targets=(),
            )

    def sync(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult:
        """
        Queue a synchronization of a preset's current state to every
        target it has previously been associated with, including any
        that are currently pending retry after a prior failure.

        Presets that have never been associated with a target have
        nothing to synchronize, so calling this is a no-op for them.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError:
                If the preset ID is None or blank, or no preset is
                registered under it
        """

        self._validate_identifier(preset_id, "preset ID")

        with self._lock:
            self._resolve_preset(preset_id)

            targets = set(self._known_targets.get(preset_id, set())) | set(
                self._failed_targets.get(preset_id, set())
            )

        synchronized_targets = []

        for target in sorted(targets):
            result = self.sync_target(preset_id, target)
            synchronized_targets.extend(result.synchronized_targets)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult(
            synchronized=bool(synchronized_targets),
            synchronized_targets=tuple(synchronized_targets),
            failed_targets=(),
        )

    def sync_all(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult:
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
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            pending_requests = self._pending
            self._pending = ()

            synchronized_targets = []
            failed_targets = []

            for request in pending_requests:
                if self._target_gateway.push(request.preset_id, request.target):
                    preset = self._preset_registry.find(request.preset_id)

                    self._synchronized_state[(request.preset_id, request.target)] = self._snapshot(
                        request.preset_id, preset
                    )
                    self._failed_targets.get(request.preset_id, set()).discard(request.target)

                    synchronized_targets.append(request.target)
                else:
                    self._failed_targets.setdefault(request.preset_id, set()).add(request.target)

                    failed_targets.append(request.target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncResult(
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

    def is_synchronized(self, preset_id: str) -> bool:
        """
        Check whether a preset is fully synchronized: it has at
        least one target it has been synchronized to, and no target
        is currently pending or failed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError:
                If the preset ID is None or blank
        """

        self._validate_identifier(preset_id, "preset ID")

        with self._lock:
            if self._failed_targets.get(preset_id):
                return False

            if any(pending.preset_id == preset_id for pending in self._pending):
                return False

            return bool(self._known_targets.get(preset_id))

    def _is_up_to_date(self, preset_id: str, target: str, preset) -> bool:
        return self._synchronized_state.get((preset_id, target)) == self._snapshot(preset_id, preset)

    def _snapshot(self, preset_id: str, preset) -> tuple:
        try:
            version_id = self._preset_version_service.latest(preset_id).version
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError:
            version_id = None

        latest_release = self._release_service.latest_release(preset_id)
        released_version = latest_release.version if latest_release is not None else None

        return (tuple(preset.binding_template_ids), version_id, released_version)

    def _resolve_preset(self, preset_id: str):
        preset = self._preset_registry.find(preset_id)

        if preset is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError(
                f"Cannot synchronize: no preset is registered under preset ID {preset_id!r}."
            )

        return preset

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetSyncError(
                f"Cannot synchronize with an empty or blank {label}."
            )
