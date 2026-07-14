from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_receipt_verification_issue_code import (
    ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReceiptVerificationIssue:
    """
    One specific verification issue detected during receipt verification.

    Identifies a mismatch between the receipt and the finalized execution
    artifacts. Does not dump entire projection payloads, provenance graphs,
    or diagnostic reports - only compact, safe values when relevant.

    Attributes:
        code: The specific issue code
        message: Human-readable description of the issue
        expected: Optional expected value (if compact and safe)
        actual: Optional actual value (if compact and safe)
    """

    code: (
        ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode
    )

    message: str

    expected: (
        Optional[str]
    ) = None

    actual: (
        Optional[str]
    ) = None
