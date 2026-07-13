from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ResearchWorkspaceCapabilityDescriptor:
    """
    Describes one high-level workspace
    capability and its public operations.
    """

    name: str

    description: str

    operations: list[
        str
    ] = field(
        default_factory=list,
    )

    version: str = (
        "1.0"
    )

    enabled: bool = True

    def to_dict(self):

        return {

            "name":
                self.name,

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
