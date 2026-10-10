from backend.session import (
    ResearchCheckpoint,
    ResearchCheckpointReason,
    ResearchIntegritySeverity,
    ResearchSessionBranch,
)

from frontend.src.app import (
    PreReqAIApplication,
)

from datetime import (
    datetime,
    timezone,
)


def create_complex_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root"
    )

    application.save_research_session(
        "root"
    )

    application.update_research_session_profile(

        "root",

        display_name="Root",
    )

    cp1 = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "math"
        ),

        display_name=(
            "Mathematical Route"
        ),
    )

    application.activate_research_session(
        "math"
    )

    cp2 = (

        application
        .checkpoint_workflow_progress(
            "s2"
        )
    )

    application.branch_research_checkpoint(

        cp2.id,

        branch_session_id=(
            "spectral"
        ),

        display_name=(
            "Spectral Route"
        ),
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "implementation"
        ),

        display_name=(
            "Implementation Route"
        ),
    )

    application.tag_research_session(

        "root",

        "transformers",
    )

    application.tag_research_session(

        "math",

        "transformers",
    )

    collection = (

        application
        .create_research_collection(

            "Current Research"
        )
    )

    application.add_research_session_to_collection(

        collection.id,

        "root",
    )

    application.compare_research_sessions(

        "root",

        "math",
    )

    return application


def test_valid_complex_workspace_passes_integrity_audit():

    application = (
        create_complex_workspace()
    )

    report = (

        application
        .audit_research_workspace()
    )

    assert (

        report.is_healthy

        is True
    )

    assert (

        report.has_critical_findings

        is False
    )


def test_auditor_detects_orphan_checkpoint():

    application = (
        PreReqAIApplication()
    )

    application.checkpoint_store.save(

        ResearchCheckpoint(

            session_id=(
                "missing-session"
            ),

            reason=(

                ResearchCheckpointReason
                .MANUAL
            ),

            snapshot_updated_at=(

                datetime.now(
                    timezone.utc
                )
            ),
        )
    )

    report = (

        application
        .audit_research_workspace()
    )

    assert any(

        finding.code

        == "orphan_checkpoint"

        for finding

        in report.findings
    )


def test_auditor_detects_session_without_profile():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    report = (

        application
        .audit_research_workspace()
    )

    finding = next(

        finding

        for finding

        in report.findings

        if (

            finding.code

            == "missing_profile"
        )
    )

    assert (

        finding.severity

        == ResearchIntegritySeverity
        .WARNING
    )


def test_auditor_detects_missing_branch_parent():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-child"
    )

    application.save_research_session(
        "session-child"
    )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id=(
                "missing-parent"
            ),

            source_checkpoint_id=(
                "checkpoint-x"
            ),

            source_version_id=(
                "version-x"
            ),

            branch_session_id=(
                "session-child"
            ),
        )
    )

    report = (

        application
        .audit_research_workspace()
    )

    assert any(

        finding.code

        == "dangling_branch_parent"

        for finding

        in report.findings
    )


def test_auditor_detects_self_branch():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id=(
                "session-a"
            ),

            source_checkpoint_id=(
                "checkpoint-x"
            ),

            source_version_id=(
                "version-x"
            ),

            branch_session_id=(
                "session-a"
            ),
        )
    )

    report = (

        application
        .audit_research_workspace()
    )

    finding = next(

        finding

        for finding

        in report.findings

        if (

            finding.code

            == "self_branch"
        )
    )

    assert (

        finding.severity

        == ResearchIntegritySeverity
        .CRITICAL
    )


def test_auditor_detects_lineage_cycle():

    application = (
        PreReqAIApplication()
    )

    for session_id in (

        "a",
        "b",
        "c",
    ):

        application.activate_research_session(
            session_id
        )

        application.save_research_session(
            session_id
        )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id="a",

            source_checkpoint_id=(
                "cp1"
            ),

            source_version_id=(
                "v1"
            ),

            branch_session_id="b",
        )
    )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id="b",

            source_checkpoint_id=(
                "cp2"
            ),

            source_version_id=(
                "v2"
            ),

            branch_session_id="c",
        )
    )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id="c",

            source_checkpoint_id=(
                "cp3"
            ),

            source_version_id=(
                "v3"
            ),

            branch_session_id="a",
        )
    )

    report = (

        application
        .audit_research_workspace()
    )

    findings = [

        finding

        for finding

        in report.findings

        if (

            finding.code

            == "lineage_cycle"
        )
    ]

    assert len(findings) == 1

    assert (

        findings[0].severity

        == ResearchIntegritySeverity
        .CRITICAL
    )


def test_auditor_detects_multiple_branch_parents():

    application = (
        PreReqAIApplication()
    )

    for session_id in (

        "parent-a",
        "parent-b",
        "child",
    ):

        application.activate_research_session(
            session_id
        )

        application.save_research_session(
            session_id
        )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id=(
                "parent-a"
            ),

            source_checkpoint_id=(
                "cp1"
            ),

            source_version_id=(
                "v1"
            ),

            branch_session_id=(
                "child"
            ),
        )
    )

    extra = ResearchSessionBranch(

        source_session_id=(
            "parent-b"
        ),

        source_checkpoint_id=(
            "cp2"
        ),

        source_version_id=(
            "v2"
        ),

        branch_session_id=(
            "child"
        ),
    )

    application.session_branch_store._branches[

        extra.id

    ] = extra

    report = (

        application
        .audit_research_workspace()
    )

    assert any(

        finding.code

        == "multiple_branch_parents"

        for finding

        in report.findings
    )


def test_duplicate_branch_generates_safe_repair_action():

    application = (
        PreReqAIApplication()
    )

    for session_id in (

        "parent",
        "child",
    ):

        application.activate_research_session(
            session_id
        )

        application.save_research_session(
            session_id
        )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id=(
                "parent"
            ),

            source_checkpoint_id=(
                "cp1"
            ),

            source_version_id=(
                "v1"
            ),

            branch_session_id=(
                "child"
            ),
        )
    )

    duplicate = ResearchSessionBranch(

        source_session_id=(
            "parent"
        ),

        source_checkpoint_id=(
            "cp2"
        ),

        source_version_id=(
            "v2"
        ),

        branch_session_id=(
            "child"
        ),
    )

    application.session_branch_store._branches[

        duplicate.id

    ] = duplicate

    report = (

        application
        .audit_research_workspace()
    )

    plan = (

        application
        .plan_research_workspace_repairs(

            report
        )
    )

    action = next(

        action

        for action

        in plan.actions

        if (

            action.finding_code

            == "duplicate_branch"
        )
    )

    from backend.session import (
        ResearchRepairRisk,
    )

    assert (

        action.risk

        == ResearchRepairRisk.SAFE
    )

    assert action.automatic is True


def test_lineage_cycle_never_generates_automatic_repair():

    application = (
        PreReqAIApplication()
    )

    for session_id in (

        "a",
        "b",
        "c",
    ):

        application.activate_research_session(
            session_id
        )

        application.save_research_session(
            session_id
        )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id="a",

            source_checkpoint_id=(
                "cp1"
            ),

            source_version_id=(
                "v1"
            ),

            branch_session_id="b",
        )
    )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id="b",

            source_checkpoint_id=(
                "cp2"
            ),

            source_version_id=(
                "v2"
            ),

            branch_session_id="c",
        )
    )

    application.session_branch_store.save(

        ResearchSessionBranch(

            source_session_id="c",

            source_checkpoint_id=(
                "cp3"
            ),

            source_version_id=(
                "v3"
            ),

            branch_session_id="a",
        )
    )

    report = (

        application
        .audit_research_workspace()
    )

    plan = (

        application
        .plan_research_workspace_repairs(

            report
        )
    )

    action = next(

        action

        for action

        in plan.actions

        if (

            action.finding_code

            == "lineage_cycle"
        )
    )

    assert action.automatic is False


def test_workspace_audit_does_not_mutate_state():

    application = (
        create_complex_workspace()
    )

    before = (

        application
        .export_research_workspace()
        .to_dict()
    )

    before.pop("manifest")

    application.audit_research_workspace()

    after = (

        application
        .export_research_workspace()
        .to_dict()
    )

    after.pop("manifest")

    assert before == after


def test_repair_planning_does_not_mutate_state():

    application = (
        create_complex_workspace()
    )

    before = (

        application
        .export_research_workspace()
        .to_dict()
    )

    before.pop("manifest")

    report = (

        application
        .audit_research_workspace()
    )

    application.plan_research_workspace_repairs(

        report
    )

    after = (

        application
        .export_research_workspace()
        .to_dict()
    )

    after.pop("manifest")

    assert before == after


def test_imported_valid_snapshot_passes_workspace_audit():

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    target = (
        PreReqAIApplication()
    )

    target.import_research_snapshot(
        snapshot
    )

    report = (

        target
        .audit_research_workspace()
    )

    assert report.is_healthy is True


def test_failed_import_rollback_preserves_workspace_integrity():

    from backend.session import (
        ResearchSnapshotImportStrategy,
    )

    application = (
        create_complex_workspace()
    )

    other = (
        create_complex_workspace()
    )

    snapshot = (

        other
        .export_research_workspace()
    )

    def failing_save(

        *args,

        **kwargs,

    ):

        raise RuntimeError(
            "simulated failure"
        )

    application.session_version_store.save = (
        failing_save
    )

    try:

        application.import_research_snapshot(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_ALL
            ),
        )

    except RuntimeError:

        pass

    report = (

        application
        .audit_research_workspace()
    )

    assert report.is_healthy is True
