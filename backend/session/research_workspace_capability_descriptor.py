from dataclasses import (
    dataclass,
)

from .research_workspace_capability import (
    ResearchWorkspaceCapability,
)


@dataclass(frozen=True)
class ResearchWorkspaceCapabilityDescriptor:
    """
    Describes one high-level workspace
    capability and its public operations.

    Frozen to ensure immutability.
    """

    capability: (
        ResearchWorkspaceCapability
    )

    description: str

    operations: tuple[
        str,
        ...
    ]

    version: str = (
        "1.0"
    )

    enabled: bool = True

    def to_dict(self):

        return {

            "capability":
                self.capability.value,

            "description":
                self.description,

            "operations":
                list(
                    self.operations
                ),

            "version":
                self.version,

            "enabled":
                self.enabled,
        }
