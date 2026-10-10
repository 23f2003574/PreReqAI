from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_readiness_check import (
    ResearchWorkspaceReadinessCheck,
)

from .research_workspace_readiness_status import (
    ResearchWorkspaceReadinessStatus,
)


@dataclass
class ResearchWorkspaceReadinessAssessment:
    """
    Aggregates readiness checks into a
    consumer-facing operational assessment.
    """

    status: (
        ResearchWorkspaceReadinessStatus
    )

    ready: bool

    blocking: bool

    checks: list[
        ResearchWorkspaceReadinessCheck
    ] = field(
        default_factory=list,
    )

    warnings: list[
        str
    ] = field(
        default_factory=list,
    )

    blocking_reasons: list[
        str
    ] = field(
        default_factory=list,
    )

    def to_dict(self):

        return {

            "status":
                self.status.value,

            "ready":
                self.ready,

            "blocking":
                self.blocking,

            "warnings":
                list(
                    self.warnings
                ),

            "blocking_reasons":
                list(
                    self.blocking_reasons
                ),

            "checks": [

                check.to_dict()

                for check

                in self.checks
            ],
        }
