from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy template versions through a
    controlled release lifecycle (DRAFT -> RELEASED -> RETIRED)
    before they may be deployed.

    The service's responsibility is release status tracking, not
    deployment, template registration, or version publication. It
    does NOT deploy templates, register templates, publish versions,
    mutate an existing release record, persist state externally,
    log, or publish events. Every transition produces a new,
    immutable release record; no release record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state
    - Forward-only: A version may only move DRAFT -> RELEASED ->
      RETIRED, never backward or sideways
    - One active release per version: A version cannot be released
      twice without an intervening retirement having never occurred;
      re-releasing an already-released or already-retired version is
      rejected
    """

    def __init__(self):

        self._releases = {}

        self._lock = RLock()

    def release(

        self,

        template_id,

        version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseResult:
        """
        Release a template version, promoting it from DRAFT to
        RELEASED.

        Args:
            template_id: The identifier of the template the version
                belongs to
            version: The version to release

        Returns:
            An immutable release result carrying the new release
            record

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError:
                If the template ID or version is None or blank, the
                version has already been released, or the version
                has already been retired
        """

        key = self._key(

            template_id,

            version,
        )

        with self._lock:

            existing = self._releases.get(
                key
            )

            if existing is not None:

                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus.RELEASED:

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError(
                            f"Cannot release version {version!r} of "
                            f"template {template_id!r}: it has already "
                            "been released."
                        )
                    )

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError(
                        f"Cannot release version {version!r} of template "
                        f"{template_id!r}: it is retired and cannot be "
                        "released again."
                    )
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus.DRAFT

            new_release = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRelease(
                    template_id=template_id,

                    version=version,

                    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus.RELEASED,

                    released_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

            self._releases[key] = new_release

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseResult(
                    previous_status=previous_status,

                    current_status=new_release.status,

                    release=new_release,
                )
            )

    def retire(

        self,

        template_id,

        version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseResult:
        """
        Retire a released template version, demoting it from
        RELEASED to RETIRED.

        Args:
            template_id: The identifier of the template the version
                belongs to
            version: The version to retire

        Returns:
            An immutable release result carrying the new release
            record

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError:
                If the template ID or version is None or blank, the
                version has never been released, or the version has
                already been retired
        """

        key = self._key(

            template_id,

            version,
        )

        with self._lock:

            existing = self._releases.get(
                key
            )

            if existing is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError(
                        f"Cannot retire version {version!r} of template "
                        f"{template_id!r}: it has never been released."
                    )
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus.RETIRED:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError(
                        f"Cannot retire version {version!r} of template "
                        f"{template_id!r}: it has already been retired."
                    )
                )

            new_release = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRelease(
                    template_id=template_id,

                    version=version,

                    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus.RETIRED,

                    released_at=existing.released_at,
                )
            )

            self._releases[key] = new_release

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseResult(
                    previous_status=existing.status,

                    current_status=new_release.status,

                    release=new_release,
                )
            )

    def latest_release(

        self,

        template_id,

    ):
        """
        Find the most recently released, currently active release
        for a template.

        Args:
            template_id: The template ID to look up

        Returns:
            The release record with status RELEASED and the latest
            released_at for the template, or None if the template
            has no currently released version

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError:
                If the template ID is None or blank
        """

        self._validate_identifier(

            template_id,

            "template ID",
        )

        with self._lock:

            candidates = [

                release

                for release

                in self._releases.values()

                if (

                    release.template_id == template_id

                    and release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus.RELEASED
                )
            ]

        if not candidates:

            return None

        return max(

            candidates,

            key=lambda release: release.released_at,
        )

    def is_released(

        self,

        template_id,

        version,

    ) -> bool:
        """
        Check whether a template version currently holds RELEASED
        status.

        Args:
            template_id: The identifier of the template the version
                belongs to
            version: The version to check

        Returns:
            True if the version's current status is RELEASED, False
            otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError:
                If the template ID or version is None or blank
        """

        key = self._key(

            template_id,

            version,
        )

        with self._lock:

            existing = self._releases.get(
                key
            )

        return (

            existing is not None

            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus.RELEASED
        )

    def _key(

        self,

        template_id,

        version,

    ):

        self._validate_identifier(

            template_id,

            "template ID",
        )

        self._validate_identifier(

            version,

            "version",
        )

        return (

            template_id,

            version,
        )

    def _validate_identifier(

        self,

        identifier,

        label,

    ) -> None:

        if (

            identifier is None

            or not identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError(
                    f"Cannot operate with an empty or blank {label}."
                )
            )
