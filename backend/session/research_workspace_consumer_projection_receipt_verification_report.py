from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_receipt_verification_issue import (
    ResearchWorkspaceConsumerProjectionReceiptVerificationIssue,
)

from .research_workspace_consumer_projection_receipt_verification_status import (
    ResearchWorkspaceConsumerProjectionReceiptVerificationStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReceiptVerificationReport:
    """
    Result of verifying a receipt against finalized execution artifacts.

    The verification report answers:
    - Is this receipt internally consistent with the execution artifacts?
    - Which specific mismatches were detected?

    Semantics:
    - No issues → VERIFIED
    - One or more issues → INVALID

    The report does not perform compatibility analysis (e.g., are contract
    versions compatible?). It only asks: does the receipt accurately describe
    this execution?

    Attributes:
        status: Overall verification status (VERIFIED or INVALID)
        issues: Tuple of detected verification issues (empty if VERIFIED)
    """

    status: (
        ResearchWorkspaceConsumerProjectionReceiptVerificationStatus
    )

    issues: tuple[
        ResearchWorkspaceConsumerProjectionReceiptVerificationIssue,
        ...
    ]

    def to_dict(self):
        """
        Serialize the verification report to a dictionary.
        """

        return {
            "status": self.status.value,
            "issues": [
                {
                    "code": issue.code.value,
                    "message": issue.message,
                    "expected": issue.expected,
                    "actual": issue.actual,
                }
                for issue in self.issues
            ],
        }
