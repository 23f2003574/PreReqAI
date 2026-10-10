from dataclasses import (
    dataclass,
    field,
)

from typing import (
    Any,
)

from .research_integrity_severity import (
    ResearchIntegritySeverity,
)


@dataclass
class ResearchIntegrityFinding:
    """
    Represents one detected workspace
    integrity problem.
    """

    code: str

    severity: (
        ResearchIntegritySeverity
    )

    message: str

    entity_type: (
        str | None
    ) = None

    entity_id: (
        str | None
    ) = None

    related_entity_ids: list[
        str
    ] = field(
        default_factory=list,
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    def to_dict(self):

        return {

            "code":
                self.code,

            "severity":
                self.severity.value,

            "message":
                self.message,

            "entity_type":
                self.entity_type,

            "entity_id":
                self.entity_id,

            "related_entity_ids":
                list(
                    self.related_entity_ids
                ),

            "metadata":
                dict(
                    self.metadata
                ),
        }
