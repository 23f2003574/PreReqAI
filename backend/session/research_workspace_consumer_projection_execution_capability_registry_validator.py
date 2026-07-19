from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)

from .research_workspace_consumer_projection_execution_capability_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_validation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_validation_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationReport,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator:
    """
    Inspects a consumer projection execution capability registry
    for integrity before it is consumed by downstream components.

    The validator's responsibility is inspection, not repair. It
    does NOT modify the registry, replace packages, repair invalid
    entries, or recompute capability decisions.

    The validator is:
    - Stateless: No instance state
    - Deterministic: Same registry state always produces the same
      report
    - Side-effect free: Never mutates the registry or its packages
    """

    def validate(

        self,

        registry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationReport:
        """
        Validate the integrity of every package registered in a
        consumer projection execution capability registry.

        Args:
            registry: The registry to validate

        Returns:
            An immutable validation report summarizing how many
            packages were inspected and how many were valid

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError:
                If the registry is None, is not a registry, or
                contains an entry that cannot be inspected
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError(
                    "Cannot validate a None registry."
                )
            )

        if not isinstance(

            registry,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError(
                    "Cannot validate registry: registry must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry."
                )
            )

        total_packages = 0

        valid_packages = 0

        invalid_packages = 0

        for projection_name in registry.list_projection_names():

            package = registry.get(
                projection_name
            )

            total_packages += 1

            if self._is_valid(
                package
            ):

                valid_packages += 1

            else:

                invalid_packages += 1

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationReport(

                total_packages=total_packages,

                valid_packages=valid_packages,

                invalid_packages=invalid_packages,

                is_valid=(
                    invalid_packages == 0
                ),
            )
        )

    @staticmethod
    def _is_valid(

        package,

    ):

        try:

            projection_name = (
                package.projection_name
            )

            decision = (
                package.decision
            )

            executable = (
                package.executable
            )

            title = (
                package.title
            )

            message = (
                package.message
            )

        except AttributeError as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError(
                    "Cannot validate registry: a registered entry "
                    "cannot be inspected as an execution "
                    f"capability decision package ({error})."
                )
            ) from error

        if not isinstance(

            projection_name,

            str,
        ) or not projection_name:

            return False

        if not isinstance(

            decision,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
        ):

            return False

        if not isinstance(

            executable,

            bool,
        ):

            return False

        if not isinstance(

            title,

            str,
        ) or not title:

            return False

        if not isinstance(

            message,

            str,
        ) or not message:

            return False

        return True
