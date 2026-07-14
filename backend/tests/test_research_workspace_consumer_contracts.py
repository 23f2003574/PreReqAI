import pytest

from backend.session import (
    ResearchWorkspaceConsumerContractDescriptor,
    ResearchWorkspaceConsumerContractId,
    ResearchWorkspaceConsumerContractManifestProvider,
    ResearchWorkspaceConsumerContractParameter,
    ResearchWorkspaceConsumerContractParameterType,
    ResearchWorkspaceConsumerContractRegistry,
    ResearchWorkspaceConsumerContractScope,
    ResearchWorkspaceConsumerContractStability,
    ResearchWorkspaceConsumerContractVersion,
)

from frontend.src.app import (
    PreReqAIApplication,
)


EXPECTED_CONTRACT_IDS = {

    "workspace.capabilities",

    "workspace.readiness",

    "workspace.bootstrap",

    "workspace.attention",

    "workspace.actions",

    "session.actions",
}


def make_descriptor(

    contract_id,

    scope=(

        ResearchWorkspaceConsumerContractScope
        .WORKSPACE
    ),

    stability=(

        ResearchWorkspaceConsumerContractStability
        .STABLE
    ),

    parameters=(),

):

    return (

        ResearchWorkspaceConsumerContractDescriptor(

            contract_id=contract_id,

            version=(

                ResearchWorkspaceConsumerContractVersion(

                    major=1,

                    minor=0,
                )
            ),

            scope=scope,

            stability=stability,

            description="Test contract.",

            projection_name="TestProjection",

            read_only=True,

            parameters=list(
                parameters
            ),

            required_capabilities=[],
        )
    )


def test_registry_contains_expected_initial_contracts():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    identifiers = {

        descriptor.contract_id.value

        for descriptor

        in registry.list_contracts()
    }

    assert identifiers == (
        EXPECTED_CONTRACT_IDS
    )


def test_contract_ids_are_unique():

    duplicate = (

        ResearchWorkspaceConsumerContractId
        .WORKSPACE_BOOTSTRAP
    )

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerContractRegistry(

            contracts=(

                make_descriptor(
                    duplicate
                ),

                make_descriptor(
                    duplicate
                ),
            ),
        )


def test_contract_lookup_works():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    by_enum = registry.get_contract(

        ResearchWorkspaceConsumerContractId
        .WORKSPACE_BOOTSTRAP
    )

    by_string = registry.get_contract(
        "workspace.bootstrap"
    )

    assert by_enum is by_string


def test_unknown_contract_is_handled_cleanly():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    assert (

        registry.get_contract(
            "workspace.unknown"
        )

        is None
    )


def test_scope_filtering_works():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    session_scoped = (

        registry.list_by_scope(

            ResearchWorkspaceConsumerContractScope
            .SESSION
        )
    )

    identifiers = {

        descriptor.contract_id.value

        for descriptor

        in session_scoped
    }

    assert identifiers == {
        "session.actions",
    }


def test_stability_filtering_works():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    stable = (

        registry.list_by_stability(

            ResearchWorkspaceConsumerContractStability
            .STABLE
        )
    )

    identifiers = {

        descriptor.contract_id.value

        for descriptor

        in stable
    }

    assert identifiers == (
        EXPECTED_CONTRACT_IDS
    )


def test_parameter_names_are_unique_within_a_contract():

    duplicate_parameters = (

        ResearchWorkspaceConsumerContractParameter(

            name="limit",

            required=False,

            value_type=(

                ResearchWorkspaceConsumerContractParameterType
                .INTEGER
            ),

            description="First.",
        ),

        ResearchWorkspaceConsumerContractParameter(

            name="limit",

            required=False,

            value_type=(

                ResearchWorkspaceConsumerContractParameterType
                .INTEGER
            ),

            description="Second.",
        ),
    )

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerContractRegistry(

            contracts=(

                make_descriptor(

                    ResearchWorkspaceConsumerContractId
                    .WORKSPACE_ATTENTION,

                    parameters=(
                        duplicate_parameters
                    ),
                ),
            ),
        )


def test_contract_version_validation():

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerContractVersion(

            major=-1,

            minor=0,
        )

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerContractVersion(

            major=1,

            minor=-2,
        )


def test_manifest_has_explicit_version():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    provider = (

        ResearchWorkspaceConsumerContractManifestProvider(
            contract_registry=registry,
        )
    )

    manifest = provider.get_manifest()

    assert (
        manifest.manifest_version.major

        == 1
    )

    assert (
        manifest.manifest_version.minor

        == 0
    )


def test_manifest_ordering_is_deterministic():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    provider = (

        ResearchWorkspaceConsumerContractManifestProvider(
            contract_registry=registry,
        )
    )

    first = [

        descriptor.contract_id.value

        for descriptor

        in provider.get_manifest().contracts
    ]

    second = [

        descriptor.contract_id.value

        for descriptor

        in provider.get_manifest().contracts
    ]

    assert first == second


def test_manifest_filtering_preserves_correct_count():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    provider = (

        ResearchWorkspaceConsumerContractManifestProvider(
            contract_registry=registry,
        )
    )

    full_manifest = provider.get_manifest()

    assert full_manifest.total_count == 6

    workspace_manifest = (

        provider.get_manifest(
            scope=(

                ResearchWorkspaceConsumerContractScope
                .WORKSPACE
            ),
        )
    )

    assert workspace_manifest.total_count == 5

    assert (

        len(
            workspace_manifest.contracts
        )

        == 5
    )


def test_manifest_generation_does_not_assess_readiness():

    application = (
        PreReqAIApplication()
    )

    original_assess = (

        application
        .research_workspace_readiness_assessor
        .assess
    )

    calls = {
        "count": 0,
    }

    def counting_assess():

        calls[
            "count"
        ] += 1

        return original_assess()

    application.research_workspace_readiness_assessor.assess = (
        counting_assess
    )

    application.research_workspace.get_consumer_contract_manifest()

    assert calls[
        "count"
    ] == 0


def test_manifest_generation_does_not_use_projection_context():

    application = (
        PreReqAIApplication()
    )

    original_create = (

        application
        .research_workspace_projection_context_factory
        .create
    )

    calls = {
        "count": 0,
    }

    def counting_create():

        calls[
            "count"
        ] += 1

        return original_create()

    application.research_workspace_projection_context_factory.create = (
        counting_create
    )

    application.research_workspace.get_consumer_contract_manifest()

    assert calls[
        "count"
    ] == 0


def test_same_major_and_newer_minor_is_compatible():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    result = registry.check_compatibility(

        "workspace.bootstrap",

        ResearchWorkspaceConsumerContractVersion(

            major=1,

            minor=0,
        ),
    )

    assert result.compatible is True


def test_requested_newer_minor_is_incompatible():

    contracts = (

        make_descriptor(

            ResearchWorkspaceConsumerContractId
            .WORKSPACE_BOOTSTRAP,
        ),
    )

    registry = (

        ResearchWorkspaceConsumerContractRegistry(
            contracts=contracts,
        )
    )

    result = registry.check_compatibility(

        "workspace.bootstrap",

        ResearchWorkspaceConsumerContractVersion(

            major=1,

            minor=3,
        ),
    )

    assert result.compatible is False


def test_different_major_is_incompatible():

    contracts = (

        make_descriptor(

            ResearchWorkspaceConsumerContractId
            .WORKSPACE_BOOTSTRAP,
        ),
    )

    registry = (

        ResearchWorkspaceConsumerContractRegistry(
            contracts=contracts,
        )
    )

    result = registry.check_compatibility(

        "workspace.bootstrap",

        ResearchWorkspaceConsumerContractVersion(

            major=2,

            minor=0,
        ),
    )

    assert result.compatible is False


def test_exact_version_is_compatible():

    contracts = (

        make_descriptor(

            ResearchWorkspaceConsumerContractId
            .WORKSPACE_BOOTSTRAP,
        ),
    )

    registry = (

        ResearchWorkspaceConsumerContractRegistry(
            contracts=contracts,
        )
    )

    result = registry.check_compatibility(

        "workspace.bootstrap",

        ResearchWorkspaceConsumerContractVersion(

            major=1,

            minor=0,
        ),
    )

    assert result.compatible is True


def test_gateway_exposes_manifest_discovery():

    application = (
        PreReqAIApplication()
    )

    gateway_manifest = (

        application
        .research_workspace
        .get_consumer_contract_manifest()
    )

    direct_manifest = (

        application
        .research_workspace_consumer_contract_manifest_provider
        .get_manifest()
    )

    assert (

        gateway_manifest.total_count

        == direct_manifest.total_count
    )


def test_gateway_exposes_contract_compatibility_check():

    application = (
        PreReqAIApplication()
    )

    result = (

        application
        .research_workspace
        .check_consumer_contract_compatibility(

            "workspace.bootstrap",

            ResearchWorkspaceConsumerContractVersion(

                major=1,

                minor=0,
            ),
        )
    )

    assert result.compatible is True


def test_serialization_uses_primitive_values():

    application = (
        PreReqAIApplication()
    )

    manifest = (

        application
        .research_workspace
        .get_consumer_contract_manifest()
    )

    payload = manifest.to_dict()

    bootstrap_payload = next(

        contract

        for contract

        in payload["contracts"]

        if (

            contract["contract_id"]

            == "workspace.bootstrap"
        )
    )

    assert (
        bootstrap_payload["scope"]

        == "workspace"
    )

    assert (
        bootstrap_payload["stability"]

        == "stable"
    )

    assert isinstance(
        bootstrap_payload["contract_id"],
        str,
    )

    attention_payload = next(

        contract

        for contract

        in payload["contracts"]

        if (

            contract["contract_id"]

            == "workspace.attention"
        )
    )

    category_parameter = next(

        parameter

        for parameter

        in attention_payload["parameters"]

        if parameter["name"] == "category"
    )

    assert (
        category_parameter["value_type"]

        == "enum"
    )


def test_manifest_generation_is_read_only():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    before_session_count = len(

        application
        .session_manager
        .list_sessions()
    )

    before_sequence = (

        application
        .research_workspace_change_feed
        .latest_sequence
    )

    before_findings = len(

        application
        .research_workspace_integrity_auditor
        .audit()
        .findings
    )

    application.research_workspace.get_consumer_contract_manifest()

    application.research_workspace.check_consumer_contract_compatibility(

        "workspace.bootstrap",

        ResearchWorkspaceConsumerContractVersion(

            major=1,

            minor=0,
        ),
    )

    after_session_count = len(

        application
        .session_manager
        .list_sessions()
    )

    after_sequence = (

        application
        .research_workspace_change_feed
        .latest_sequence
    )

    after_findings = len(

        application
        .research_workspace_integrity_auditor
        .audit()
        .findings
    )

    assert (
        before_session_count

        == after_session_count
    )

    assert before_sequence == after_sequence

    assert before_findings == after_findings


def test_internal_projection_context_is_not_registered():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    identifiers = {

        descriptor.contract_id.value

        for descriptor

        in registry.list_contracts()
    }

    assert (

        "workspace.projection_context"

        not in identifiers
    )


def test_individual_actions_are_not_registered_as_contracts():

    registry = (
        ResearchWorkspaceConsumerContractRegistry()
    )

    identifiers = {

        descriptor.contract_id.value

        for descriptor

        in registry.list_contracts()
    }

    assert (
        "create_branch"

        not in identifiers
    )

    assert (
        "pause_session"

        not in identifiers
    )

    assert (
        "archive_session"

        not in identifiers
    )


def test_registry_describes_actual_implemented_parameters():

    application = (
        PreReqAIApplication()
    )

    registry = (

        application
        .research_workspace_consumer_contract_registry
    )

    bootstrap_descriptor = (

        registry.get_contract(
            "workspace.bootstrap"
        )
    )

    bootstrap_parameter_names = {

        parameter.name

        for parameter

        in bootstrap_descriptor.parameters
    }

    assert bootstrap_parameter_names == {
        "recent_session_limit",

        "recent_activity_limit",
    }

    application.research_workspace.get_bootstrap(

        recent_session_limit=1,

        recent_activity_limit=1,
    )

    attention_descriptor = (

        registry.get_contract(
            "workspace.attention"
        )
    )

    attention_parameter_names = {

        parameter.name

        for parameter

        in attention_descriptor.parameters
    }

    assert attention_parameter_names == {
        "category",

        "minimum_severity",

        "actionable_only",

        "limit",
    }

    application.research_workspace.get_attention(

        category="integrity",

        minimum_severity="low",

        actionable_only=True,

        limit=5,
    )

    session_actions_descriptor = (

        registry.get_contract(
            "session.actions"
        )
    )

    session_actions_parameter_names = {

        parameter.name

        for parameter

        in session_actions_descriptor.parameters
    }

    assert session_actions_parameter_names == {
        "session_id",

        "include_unavailable",
    }
