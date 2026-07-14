from unittest.mock import (
    Mock,
)

from backend.session import (
    ResearchWorkspaceCapabilities,
    ResearchWorkspaceGateway,
)

from frontend.src.app import (
    PreReqAIApplication,
)


EXPECTED_PUBLIC_METHODS = {

    "list_capabilities",

    "get_capability",

    "supports",

    "describe",

    "assess_readiness",

    "get_bootstrap",

    "get_attention",

    "list_workspace_actions",

    "list_session_actions",

    "create_session",

    "get_session",

    "get_session_profile",

    "update_session_profile",

    "update_lifecycle_state",

    "create_checkpoint",

    "search_sessions",

    "branch_session",

    "get_lineage",

    "get_ancestors",

    "get_descendants",

    "compare_sessions",

    "create_tag",

    "assign_tag",

    "remove_tag_assignment",

    "create_collection",

    "add_collection_member",

    "remove_collection_member",

    "get_activity",

    "get_workspace_insights",

    "export_workspace",

    "serialize_snapshot",

    "preview_import",

    "import_snapshot",

    "audit_workspace",

    "plan_repairs",

    "get_changes",

    "get_latest_change_sequence",

    "subscribe",

    "unsubscribe",
}


def test_workspace_gateway_exposes_expected_capabilities():

    application = (
        PreReqAIApplication()
    )

    gateway = (

        application
        .research_workspace
    )

    names = {

        capability.name

        for capability

        in gateway.list_capabilities()
    }

    assert {

        "sessions",

        "discovery",

        "lineage",

        "comparison",

        "organization",

        "activity",

        "insights",

        "snapshots",

        "import",

        "integrity",

        "change_feed",

        "subscriptions",

    }.issubset(
        names
    )


def test_workspace_gateway_supports_capability_lookup():

    application = (
        PreReqAIApplication()
    )

    gateway = (

        application
        .research_workspace
    )

    assert (

        gateway.supports(
            "lineage"
        )

        is True
    )

    assert (

        gateway.supports(
            "does_not_exist"
        )

        is False
    )


def test_workspace_gateway_public_api_is_stable():

    application = (
        PreReqAIApplication()
    )

    gateway = (

        application
        .research_workspace
    )

    for method_name in (

        EXPECTED_PUBLIC_METHODS
    ):

        assert hasattr(

            gateway,

            method_name,
        )

        assert callable(

            getattr(

                gateway,

                method_name,
            )
        )


def test_workspace_gateway_does_not_expose_internal_stores():

    application = (
        PreReqAIApplication()
    )

    gateway = (

        application
        .research_workspace
    )

    assert not hasattr(

        gateway,

        "checkpoint_store",
    )

    assert not hasattr(

        gateway,

        "tag_store",
    )

    assert not hasattr(

        gateway,

        "activity_store",
    )


def test_gateway_create_session_delegates_to_application():

    application = Mock()

    capabilities = (

        ResearchWorkspaceCapabilities()
    )

    gateway = (

        ResearchWorkspaceGateway(

            application=application,

            capabilities=capabilities,

            readiness_assessor=Mock(),

            bootstrap_projector=Mock(),

            attention_projector=Mock(),

            action_projector=Mock(),
        )
    )

    gateway.create_session(

        "session-a",

        paper_title=(
            "Why do transformers work?"
        ),
    )

    application.activate_research_session.assert_called_once_with(

        "session-a",

        paper_id=None,

        paper_title=(
            "Why do transformers work?"
        ),
    )

    application.save_research_session.assert_called_once_with(

        "session-a",

        paper_id=None,

        paper_title=(
            "Why do transformers work?"
        ),
    )


def test_gateway_search_sessions_delegates_to_application():

    application = Mock()

    capabilities = (

        ResearchWorkspaceCapabilities()
    )

    gateway = (

        ResearchWorkspaceGateway(

            application=application,

            capabilities=capabilities,

            readiness_assessor=Mock(),

            bootstrap_projector=Mock(),

            attention_projector=Mock(),

            action_projector=Mock(),
        )
    )

    gateway.search_sessions(
        search="transformers"
    )

    application.query_research_sessions.assert_called_once_with(
        search="transformers"
    )


def test_gateway_compare_sessions_delegates_to_application():

    application = Mock()

    capabilities = (

        ResearchWorkspaceCapabilities()
    )

    gateway = (

        ResearchWorkspaceGateway(

            application=application,

            capabilities=capabilities,

            readiness_assessor=Mock(),

            bootstrap_projector=Mock(),

            attention_projector=Mock(),

            action_projector=Mock(),
        )
    )

    gateway.compare_sessions(

        "session-a",

        "session-b",
    )

    application.compare_research_sessions.assert_called_once_with(

        "session-a",

        "session-b",
    )


def test_gateway_export_workspace_delegates_to_application():

    application = Mock()

    capabilities = (

        ResearchWorkspaceCapabilities()
    )

    gateway = (

        ResearchWorkspaceGateway(

            application=application,

            capabilities=capabilities,

            readiness_assessor=Mock(),

            bootstrap_projector=Mock(),

            attention_projector=Mock(),

            action_projector=Mock(),
        )
    )

    gateway.export_workspace()

    application.export_research_workspace.assert_called_once_with()


def test_gateway_import_snapshot_delegates_to_application():

    application = Mock()

    capabilities = (

        ResearchWorkspaceCapabilities()
    )

    gateway = (

        ResearchWorkspaceGateway(

            application=application,

            capabilities=capabilities,

            readiness_assessor=Mock(),

            bootstrap_projector=Mock(),

            attention_projector=Mock(),

            action_projector=Mock(),
        )
    )

    fake_snapshot = object()

    gateway.import_snapshot(
        fake_snapshot
    )

    assert (

        application
        .import_research_snapshot
        .call_count

        == 1
    )

    call_args = (

        application
        .import_research_snapshot
        .call_args
    )

    assert call_args.args == (
        fake_snapshot,
    )


def test_gateway_audit_workspace_delegates_to_application():

    application = Mock()

    capabilities = (

        ResearchWorkspaceCapabilities()
    )

    gateway = (

        ResearchWorkspaceGateway(

            application=application,

            capabilities=capabilities,

            readiness_assessor=Mock(),

            bootstrap_projector=Mock(),

            attention_projector=Mock(),

            action_projector=Mock(),
        )
    )

    gateway.audit_workspace()

    application.audit_research_workspace.assert_called_once_with()


def test_gateway_get_changes_delegates_to_application():

    application = Mock()

    capabilities = (

        ResearchWorkspaceCapabilities()
    )

    gateway = (

        ResearchWorkspaceGateway(

            application=application,

            capabilities=capabilities,

            readiness_assessor=Mock(),

            bootstrap_projector=Mock(),

            attention_projector=Mock(),

            action_projector=Mock(),
        )
    )

    gateway.get_changes(
        after_sequence=5
    )

    application.get_research_workspace_changes.assert_called_once_with(

        after_sequence=5,

        limit=100,

        entity_types=None,

        operations=None,
    )


def test_gateway_describe_returns_capability_summary():

    application = (
        PreReqAIApplication()
    )

    gateway = (

        application
        .research_workspace
    )

    description = gateway.describe()

    assert (

        description["capability_count"]

        == len(
            gateway.list_capabilities()
        )
    )

    assert (

        description["latest_change_sequence"]

        == gateway.get_latest_change_sequence()
    )
