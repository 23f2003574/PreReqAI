from dataclasses import (
    dataclass,
    field,
)

from collections import (
    Counter,
)

from .research_integrity_finding import (
    ResearchIntegrityFinding,
)

from .research_integrity_severity import (
    ResearchIntegritySeverity,
)


@dataclass
class ResearchIntegrityReport:
    """
    Aggregates all integrity findings
    produced by a workspace audit.
    """

    findings: list[
        ResearchIntegrityFinding
    ] = field(
        default_factory=list,
    )

    @property
    def is_healthy(self):

        return not any(

            finding.severity

            in {

                ResearchIntegritySeverity
                .ERROR,

                ResearchIntegritySeverity
                .CRITICAL,
            }

            for finding

            in self.findings
        )

    @property
    def has_critical_findings(self):

        return any(

            finding.severity

            == ResearchIntegritySeverity
            .CRITICAL

            for finding

            in self.findings
        )

    def count_by_severity(self):

        counts = Counter(

            finding.severity.value

            for finding

            in self.findings
        )

        return dict(
            counts
        )

    def count_by_code(self):

        counts = Counter(

            finding.code

            for finding

            in self.findings
        )

        return dict(
            counts
        )

    def to_dict(self):

        return {

            "is_healthy":
                self.is_healthy,

            "has_critical_findings":
                self.has_critical_findings,

            "total_findings":
                len(
                    self.findings
                ),

            "counts_by_severity":
                self.count_by_severity(),

            "counts_by_code":
                self.count_by_code(),

            "findings": [

                finding.to_dict()

                for finding

                in self.findings
            ],
        }
