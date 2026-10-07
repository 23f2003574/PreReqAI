"""backend.session exports the consumer-projection diagnostic status under both
spellings consumers use: the module's own singular name and the plural one that
matches its sibling Diagnostics* exports. Both are the same class."""
from backend.session import (
    ResearchWorkspaceConsumerProjectionDiagnosticsCollector,
    ResearchWorkspaceConsumerProjectionDiagnosticsStatus,
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)


def test_both_spellings_name_the_same_status_class():
    assert ResearchWorkspaceConsumerProjectionDiagnosticsStatus is ResearchWorkspaceConsumerProjectionDiagnosticStatus
    assert {"SUCCEEDED", "DEGRADED", "FAILED"} <= set(ResearchWorkspaceConsumerProjectionDiagnosticsStatus.__members__)
    assert ResearchWorkspaceConsumerProjectionDiagnosticsCollector is not None  # imported alongside it, as consumers do
