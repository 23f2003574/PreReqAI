from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionGovernanceReport,
    ExecutionGovernanceReportError as Error,
    ExecutionGovernanceReportService,
)


class _FakeApprovalService:
    def __init__(self, status_by_change):
        self._status_by_change = status_by_change

    def status(self, change_id):
        if change_id not in self._status_by_change:
            raise ValueError(f"unknown change {change_id!r}")

        return self._status_by_change[change_id]

    def set_status(self, change_id, status):
        self._status_by_change[change_id] = status


class _FakeComplianceService:
    def __init__(self, compliant_by_change=None):
        self._compliant_by_change = compliant_by_change or {}

    def can_approve(self, change_id):
        if change_id not in self._compliant_by_change:
            raise ValueError(f"never evaluated {change_id!r}")

        return self._compliant_by_change[change_id]


class _FakeCertificationService:
    def __init__(self, status_by_change=None):
        self._status_by_change = status_by_change or {}

    def status(self, change_id):
        if change_id not in self._status_by_change:
            raise ValueError(f"never certified {change_id!r}")

        return self._status_by_change[change_id]


class _FakeExceptionService:
    def __init__(self, active_by_change=None):
        self._active_by_change = active_by_change or {}

    def active(self, change_id):
        return self._active_by_change.get(change_id, ())


def _exception(exception_id):
    return SimpleNamespace(exception_id=exception_id)


def _build(
    status_by_change=None,
    compliant_by_change=None,
    certification_status_by_change=None,
    active_by_change=None,
):
    approval_service = _FakeApprovalService(status_by_change or {"change-1": "APPROVED"})
    compliance_service = _FakeComplianceService(compliant_by_change)
    certification_service = _FakeCertificationService(certification_status_by_change)
    exception_service = _FakeExceptionService(active_by_change)
    report_service = ExecutionGovernanceReportService(
        approval_service, compliance_service, certification_service, exception_service
    )
    return approval_service, report_service


class TestExecutionGovernanceReportService:
    def test_generate_report(self):
        _, service = _build()

        report = service.generate("change-1")

        assert isinstance(report, ExecutionGovernanceReport)
        assert report.change_id == "change-1"

    def test_unknown_change_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.generate("never-created-change")

    def test_approval_status(self):
        _, service = _build(status_by_change={"change-1": "REJECTED"})

        report = service.generate("change-1")

        assert report.approval_status == "REJECTED"

    def test_compliance_and_certification_status(self):
        _, service = _build(
            compliant_by_change={"change-1": False},
            certification_status_by_change={"change-1": "FAILED"},
        )

        report = service.generate("change-1")

        assert report.compliance_status == "NON_COMPLIANT"
        assert report.certification_status == "FAILED"

    def test_unevaluated_and_uncertified_status(self):
        _, service = _build()

        report = service.generate("change-1")

        assert report.compliance_status == "NOT_EVALUATED"
        assert report.certification_status == "NOT_CERTIFIED"

    def test_exception_inclusion(self):
        _, service = _build(active_by_change={"change-1": (_exception("exception-2"), _exception("exception-1"))})

        report = service.generate("change-1")

        assert report.exceptions == ("exception-1", "exception-2")

    def test_deterministic_output(self):
        _, service = _build(active_by_change={"change-1": (_exception("exception-1"),)})

        first = service.generate("change-1")
        second = service.generate("change-1")

        assert first.approval_status == second.approval_status
        assert first.compliance_status == second.compliance_status
        assert first.certification_status == second.certification_status
        assert first.exceptions == second.exceptions

    def test_history(self):
        _, service = _build()

        first = service.generate("change-1")
        second = service.generate("change-1")

        assert service.history("change-1") == [first, second]

    def test_get_unknown_report_is_an_error(self):
        _, service = _build()

        with pytest.raises(Error):
            service.get("unknown-report")

    def test_report_comparison(self):
        approval_service, service = _build(status_by_change={"change-1": "PENDING"})
        before = service.generate("change-1")

        approval_service.set_status("change-1", "APPROVED")
        after = service.generate("change-1")

        comparison = service.compare(before.report_id, after.report_id)

        assert comparison["approval_status_changed"] is True

    def test_compare_unknown_report_is_an_error(self):
        _, service = _build()
        report = service.generate("change-1")

        with pytest.raises(Error):
            service.compare(report.report_id, "unknown-report")
