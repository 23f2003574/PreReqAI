from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy profile binding template versions
    through a controlled release lifecycle (DRAFT -> RELEASED ->
    RETIRED), so that only approved template version snapshots can be
    promoted into deployment. Only a (template, version) pair
    currently holding RELEASED status is deployable.

    The service's responsibility is release status tracking, not
    template creation, membership management, version publication, or
    deployment itself. It does NOT create templates, mutate template
    membership, publish template versions, deploy templates, mutate
    the template registry or version history, persist state
    externally, log, or publish events. Every transition produces a
    new, immutable release record; no release record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state, including the release identifier itself
    - Forward-only: A (template, version) pair may only move DRAFT ->
      RELEASED -> RETIRED, never backward or sideways
    - One active release per (template_id, version): Re-releasing an
      already released or already retired version is rejected
    - Append-only: Every transition appends a new record to the
      release history; no earlier record is ever mutated or removed
    """

    def __init__(self, template_registry, template_version_service):
        """
        Args:
            template_registry: The registry used to verify a template
                exists. Any object exposing `find(template_id)` is
                accepted
            template_version_service: The version service used to
                verify a version was published for the template. Any
                object exposing `find(template_id, version)` is
                accepted
        """

        if template_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                "Cannot initialize release service with a None template registry."
            )

        if template_version_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                "Cannot initialize release service with a None template version service."
            )

        self._template_registry = template_registry
        self._template_version_service = template_version_service
        self._releases = {}
        self._lock = RLock()

    def release(
        self,
        template_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseResult:
        """
        Release a template version, promoting it from DRAFT to
        RELEASED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError:
                If the template ID or version is None or blank, no
                template is registered under the template ID, no
                version was published for the template, or the
                version has already been released or retired
        """

        key = self._key(template_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is not None:
                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RELEASED:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                        f"Cannot release version {version!r} of template ID {template_id!r}: it has already been released."
                    )

                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                    f"Cannot release version {version!r} of template ID {template_id!r}: it is retired and cannot be released again."
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.DRAFT

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRelease(
                release_id=self._generate_release_id(template_id, version),
                template_id=template_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RELEASED,
                released_at=datetime.now(timezone.utc),
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseResult(
                previous_status=previous_status,
                current_status=new_release.status,
                release=new_release,
            )

    def retire(
        self,
        template_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseResult:
        """
        Retire a released template version, demoting it from RELEASED
        to RETIRED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError:
                If the template ID or version is None or blank, no
                template is registered under the template ID, no
                version was published for the template, the version
                has never been released, or it has already been
                retired
        """

        key = self._key(template_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                    f"Cannot retire version {version!r} of template ID {template_id!r}: it has never been released."
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RETIRED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                    f"Cannot retire version {version!r} of template ID {template_id!r}: it has already been retired."
                )

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRelease(
                release_id=existing.release_id,
                template_id=template_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RETIRED,
                released_at=existing.released_at,
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseResult(
                previous_status=existing.status,
                current_status=new_release.status,
                release=new_release,
            )

    def latest_release(self, template_id: str):
        """
        Find the most recently released, currently active release
        for a template.

        Returns:
            The release record with status RELEASED and the latest
            released_at for the template, or None if the template has
            no currently released version

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError:
                If the template ID is None or blank, or no template is
                registered under it
        """

        self._resolve_template(template_id)

        with self._lock:
            candidates = [
                release
                for release in self._releases.values()
                if (
                    release.template_id == template_id
                    and release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RELEASED
                )
            ]

        if not candidates:
            return None

        return max(candidates, key=lambda release: release.released_at)

    def is_released(self, template_id: str, version: str) -> bool:
        """
        Check whether a (template, version) pair currently holds
        RELEASED status. Only a version for which this returns True
        is deployable.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError:
                If the template ID or version is None or blank, no
                template is registered under the template ID, or no
                version was published for the template
        """

        key = self._key(template_id, version)

        with self._lock:
            existing = self._releases.get(key)

        return (
            existing is not None
            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RELEASED
        )

    def _key(self, template_id: str, version: str):
        self._resolve_template(template_id)

        self._validate_identifier(version, "version")

        if self._template_version_service.find(template_id, version) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                f"Cannot operate: version {version!r} was not found for template ID {template_id!r}."
            )

        return (template_id, version)

    def _resolve_template(self, template_id: str):
        self._validate_identifier(template_id, "template ID")

        template = self._template_registry.find(template_id)

        if template is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                f"Cannot operate: no template is registered under template ID {template_id!r}."
            )

        return template

    def _generate_release_id(self, template_id: str, version: str) -> str:
        return f"release::{template_id}::{version}"

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                f"Cannot operate with an empty or blank {label}."
            )
