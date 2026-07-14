from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ResearchIntegrityFinding,
    ResearchIntegrityReport,
    ResearchIntegritySeverity,
    ResearchSessionActivitySummary,
    ResearchWorkspaceAttentionProjector,
    ResearchWorkspaceBootstrapProjector,
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
    ResearchWorkspaceConsumerProjectionProvenanceCollector,
    ResearchWorkspaceConsumerProjectionProvenanceCollectorFactory,
    ResearchWorkspaceProjectionContext,
    ResearchWorkspaceProjectionContextFactory,
    ResearchWorkspaceReadinessAssessment,
    ResearchWorkspaceReadinessStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def make_readiness(

    status,

    warnings=(),

    blocking_reasons=(),

):

    return (

        ResearchWorkspaceReadinessAssessment(

            status=status,

            ready=(

                status

                != ResearchWorkspaceReadinessStatus
                .UNAVAILABLE
            ),

            blocking=(

                status

                == ResearchWorkspaceReadinessStatus
                .UNAVAILABLE
            ),

            checks=[],

            warnings=list(
                warnings
            ),

            blocking_reasons=list(
                blocking_reasons
            ),
        )
    )


class FakeReadinessAssessor:

    def __init__(

        self,

        assessment,

    ):

        self.assessment = (
            assessment
        )

    def assess(self):

        return self.assessment


class FakeIntegrityAuditor:

    def __init__(

        self,

        report=None,

    ):

        self.report = (

            report

            or ResearchIntegrityReport()
        )

    def audit(self):

        return self.report


class FakeInsightsService:

    def __init__(

        self,

        dormant_sessions=(),

    ):

        self._dormant_sessions = list(
            dormant_sessions
        )

    def build_insights(

        self,

        **kwargs,

    ):

        return (

            SimpleNamespace(

                dormant_sessions=(

                    self
                    ._dormant_sessions
                ),

                overview=SimpleNamespace(),
            )
        )


class FakeCapabilityRegistry:

    def list_capabilities(self):

        return []


def dormant_summary(

    session_id="session-842",

    display_name="Spectral Route",

    lifecycle_status="paused",

):

    return (

        ResearchSessionActivitySummary(

            session_id=session_id,

            display_name=display_name,

            lifecycle_status=(
                lifecycle_status
            ),

            archived=False,

            last_activity_at=None,

            activity_count=0,
        )
    )


def create_attention_projector(

    readiness=None,

    integrity_report=None,

    dormant_sessions=(),

):

    context_factory = (

        ResearchWorkspaceProjectionContextFactory(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    readiness

                    or make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(

                FakeIntegrityAuditor(
                    integrity_report
                )
            ),

            insights_service=(

                FakeInsightsService(
                    dormant_sessions
                )
            ),

            session_manager=None,

            profile_store=None,
        )
    )

    return (

        ResearchWorkspaceAttentionProjector(
            context_factory=context_factory,
        )
    )


# ---------------------------------------------------------------------------
# Collector: node registration
# ---------------------------------------------------------------------------


def test_collector_starts_empty():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    report = collector.build_report()

    assert report.sources == []

    assert report.derivations == []

    assert report.outputs == []

    assert report.edges == []


def test_register_source_creates_node():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    node_id = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    report = collector.build_report()

    assert len(report.sources) == 1

    assert (
        report.sources[0].node_id

        == node_id
    )

    assert (
        report.sources[0].source_name

        == "workspace.readiness"
    )


def test_register_source_deduplicates_by_name():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    first = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    second = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    assert first == second

    report = collector.build_report()

    assert len(report.sources) == 1


def test_register_source_carries_timestamp_and_freshness():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.register_source(

        source_name="workspace.recent_activity",

        source_timestamp="2026-07-14T10:00:00+00:00",

        freshness_status=(

            ResearchWorkspaceConsumerProjectionFreshnessStatus
            .FRESH
        ),
    )

    report = collector.build_report()

    source = report.sources[0]

    assert (

        source.source_timestamp

        == "2026-07-14T10:00:00+00:00"
    )

    assert (

        source.freshness_status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .FRESH
    )


def test_register_derivation_never_deduplicates():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    first = (

        collector.register_derivation(
            rule_name="attention.integrity_review_rule",
        )
    )

    second = (

        collector.register_derivation(
            rule_name="attention.integrity_review_rule",
        )
    )

    assert first != second

    report = collector.build_report()

    assert len(report.derivations) == 2


def test_register_output_creates_node():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    node_id = (

        collector.register_output(

            output_type="attention_item",

            output_key="readiness:degraded",
        )
    )

    report = collector.build_report()

    assert len(report.outputs) == 1

    assert (
        report.outputs[0].node_id

        == node_id
    )


def test_register_output_rejects_duplicate_identity():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.register_output(

        output_type="attention_item",

        output_key="readiness:degraded",
    )

    with pytest.raises(ValueError):

        collector.register_output(

            output_type="attention_item",

            output_key="readiness:degraded",
        )


def test_get_output_node_id_returns_none_when_missing():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    assert (

        collector.get_output_node_id(

            output_type="attention_item",

            output_key="missing",
        )

        is None
    )


def test_get_output_node_id_returns_registered_node():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    node_id = (

        collector.register_output(

            output_type="attention_item",

            output_key="readiness:degraded",
        )
    )

    assert (

        collector.get_output_node_id(

            output_type="attention_item",

            output_key="readiness:degraded",
        )

        == node_id
    )


def test_node_ids_are_unique_across_all_kinds():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    derivation_id = (

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )
    )

    output_id = (

        collector.register_output(

            output_type="attention_item",

            output_key="readiness:degraded",
        )
    )

    assert (

        len(
            {
                source_id,
                derivation_id,
                output_id,
            }
        )

        == 3
    )


# ---------------------------------------------------------------------------
# Collector: edges and DAG validation
# ---------------------------------------------------------------------------


def test_add_edge_creates_edge():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    derivation_id = (

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )
    )

    collector.add_edge(

        from_node_id=source_id,

        to_node_id=derivation_id,
    )

    report = collector.build_report()

    assert len(report.edges) == 1

    assert (
        report.edges[0].from_node_id

        == source_id
    )

    assert (
        report.edges[0].to_node_id

        == derivation_id
    )


def test_add_edge_rejects_self_edge():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    node_id = (

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )
    )

    with pytest.raises(ValueError):

        collector.add_edge(

            from_node_id=node_id,

            to_node_id=node_id,
        )


def test_add_edge_rejects_unknown_from_node():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    node_id = (

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )
    )

    with pytest.raises(ValueError):

        collector.add_edge(

            from_node_id="source:999",

            to_node_id=node_id,
        )


def test_add_edge_rejects_unknown_to_node():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    node_id = (

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )
    )

    with pytest.raises(ValueError):

        collector.add_edge(

            from_node_id=node_id,

            to_node_id="output:999",
        )


def test_add_edge_is_idempotent_for_duplicate_pair():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    derivation_id = (

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )
    )

    collector.add_edge(

        from_node_id=source_id,

        to_node_id=derivation_id,
    )

    collector.add_edge(

        from_node_id=source_id,

        to_node_id=derivation_id,
    )

    report = collector.build_report()

    assert len(report.edges) == 1


def test_add_edge_rejects_cycle():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    first = (

        collector.register_derivation(
            rule_name="rule.one",
        )
    )

    second = (

        collector.register_derivation(
            rule_name="rule.two",
        )
    )

    collector.add_edge(

        from_node_id=first,

        to_node_id=second,
    )

    with pytest.raises(ValueError):

        collector.add_edge(

            from_node_id=second,

            to_node_id=first,
        )


def test_record_derivation_wires_inputs_derivation_and_output():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    output_id = (

        collector.record_derivation(

            rule_name="attention.readiness_degraded_rule",

            input_node_ids=(
                source_id,
            ),

            output_type="attention_item",

            output_key="readiness:degraded",
        )
    )

    report = collector.build_report()

    assert len(report.derivations) == 1

    assert len(report.outputs) == 1

    assert len(report.edges) == 2

    assert (

        report.outputs[0].node_id

        == output_id
    )


# ---------------------------------------------------------------------------
# Collector: finalization
# ---------------------------------------------------------------------------


def test_build_report_is_idempotent():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.register_source(
        source_name="workspace.readiness",
    )

    first = collector.build_report()

    second = collector.build_report()

    assert first is second


def test_registering_source_after_finalization_is_rejected():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.build_report()

    with pytest.raises(RuntimeError):

        collector.register_source(
            source_name="workspace.readiness",
        )


def test_registering_derivation_after_finalization_is_rejected():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.build_report()

    with pytest.raises(RuntimeError):

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )


def test_registering_output_after_finalization_is_rejected():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.build_report()

    with pytest.raises(RuntimeError):

        collector.register_output(

            output_type="attention_item",

            output_key="readiness:degraded",
        )


def test_adding_edge_after_finalization_is_rejected():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.readiness",
        )
    )

    derivation_id = (

        collector.register_derivation(
            rule_name="attention.readiness_degraded_rule",
        )
    )

    collector.build_report()

    with pytest.raises(RuntimeError):

        collector.add_edge(

            from_node_id=source_id,

            to_node_id=derivation_id,
        )


def test_factory_creates_independent_collectors():

    factory = (

        ResearchWorkspaceConsumerProjectionProvenanceCollectorFactory()
    )

    first = (

        factory.create(
            operation_name="workspace.bootstrap",
        )
    )

    second = (

        factory.create(
            operation_name="workspace.bootstrap",
        )
    )

    first.register_source(
        source_name="workspace.readiness",
    )

    assert (

        first.build_report().sources

        != second.build_report().sources
    )


# ---------------------------------------------------------------------------
# Report: traversal
# ---------------------------------------------------------------------------


def test_get_ancestors_returns_upstream_nodes():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.integrity",
        )
    )

    output_id = (

        collector.record_derivation(

            rule_name="attention.integrity_review_rule",

            input_node_ids=(
                source_id,
            ),

            output_type="attention_item",

            output_key="integrity:x:y",
        )
    )

    report = collector.build_report()

    ancestors = (
        report.get_ancestors(output_id)
    )

    assert source_id in ancestors


def test_get_source_ancestors_filters_to_sources_only():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.integrity",
        )
    )

    output_id = (

        collector.record_derivation(

            rule_name="attention.integrity_review_rule",

            input_node_ids=(
                source_id,
            ),

            output_type="attention_item",

            output_key="integrity:x:y",
        )
    )

    report = collector.build_report()

    source_ancestors = (

        report.get_source_ancestors(
            output_id
        )
    )

    assert len(source_ancestors) == 1

    assert (

        source_ancestors[0].node_id

        == source_id
    )


def test_get_output_descendants_returns_downstream_outputs():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.integrity",
        )
    )

    output_id = (

        collector.record_derivation(

            rule_name="attention.integrity_review_rule",

            input_node_ids=(
                source_id,
            ),

            output_type="attention_item",

            output_key="integrity:x:y",
        )
    )

    report = collector.build_report()

    descendants = (

        report.get_output_descendants(
            source_id
        )
    )

    assert len(descendants) == 1

    assert (

        descendants[0].node_id

        == output_id
    )


def test_ancestors_of_a_source_node_is_empty():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.integrity",
        )
    )

    report = collector.build_report()

    assert (

        report.get_ancestors(source_id)

        == set()
    )


def test_descendants_of_a_leaf_output_is_empty():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.integrity",
        )
    )

    output_id = (

        collector.record_derivation(

            rule_name="attention.integrity_review_rule",

            input_node_ids=(
                source_id,
            ),

            output_type="attention_item",

            output_key="integrity:x:y",
        )
    )

    report = collector.build_report()

    assert (

        report.get_output_descendants(
            output_id
        )

        == []
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_source_provenance_to_dict_uses_primitive_values():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.register_source(

        source_name="workspace.recent_activity",

        freshness_status=(

            ResearchWorkspaceConsumerProjectionFreshnessStatus
            .STALE
        ),
    )

    report = collector.build_report()

    payload = (
        report.sources[0].to_dict()
    )

    assert (
        payload["freshness_status"]

        == "stale"
    )

    assert (

        isinstance(
            payload["freshness_status"],

            str,
        )
    )


def test_source_provenance_to_dict_handles_missing_metadata():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    collector.register_source(
        source_name="workspace.readiness",
    )

    report = collector.build_report()

    payload = (
        report.sources[0].to_dict()
    )

    assert payload["source_timestamp"] is None

    assert payload["freshness_status"] is None


def test_report_to_dict_serializes_all_collections():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    source_id = (

        collector.register_source(
            source_name="workspace.integrity",
        )
    )

    collector.record_derivation(

        rule_name="attention.integrity_review_rule",

        input_node_ids=(
            source_id,
        ),

        output_type="attention_item",

        output_key="integrity:x:y",
    )

    report = collector.build_report()

    payload = report.to_dict()

    assert (
        payload["operation_name"]

        == "workspace.attention"
    )

    assert len(payload["sources"]) == 1

    assert len(payload["derivations"]) == 1

    assert len(payload["outputs"]) == 1

    assert len(payload["edges"]) == 2

    for collection_key in (

        "sources",

        "derivations",

        "outputs",

        "edges",
    ):

        for entry in payload[collection_key]:

            assert isinstance(entry, dict)


# ---------------------------------------------------------------------------
# Context integration
# ---------------------------------------------------------------------------


def test_context_registers_source_provenance_on_first_capabilities_resolution():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    context = (

        ResearchWorkspaceProjectionContext(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,

            provenance=collector,
        )
    )

    context.get_capabilities()

    report = collector.build_report()

    assert len(report.sources) == 1

    assert (

        report.sources[0].source_name

        == "workspace.capabilities"
    )


def test_context_reuses_same_source_node_on_repeated_resolution():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    context = (

        ResearchWorkspaceProjectionContext(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,

            provenance=collector,
        )
    )

    context.get_readiness()

    context.get_readiness()

    report = collector.build_report()

    assert len(report.sources) == 1


def test_context_registers_readiness_integrity_and_insights_sources():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    context = (

        ResearchWorkspaceProjectionContext(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,

            provenance=collector,
        )
    )

    context.get_readiness()

    context.get_integrity_report()

    context.get_workspace_insights()

    report = collector.build_report()

    source_names = {

        source.source_name

        for source in report.sources
    }

    assert source_names == {

        "workspace.readiness",

        "workspace.integrity",

        "workspace.insights",
    }


def test_context_without_provenance_collector_is_a_noop():

    context = (

        ResearchWorkspaceProjectionContext(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,
        )
    )

    context.get_readiness()

    assert (

        context.get_source_provenance_node_id(
            "workspace.readiness"
        )

        is None
    )


def test_get_source_provenance_node_id_registers_lazily():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    context = (

        ResearchWorkspaceProjectionContext(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,

            provenance=collector,
        )
    )

    node_id = (

        context.get_source_provenance_node_id(
            "workspace.readiness"
        )
    )

    assert node_id is not None

    report = collector.build_report()

    assert len(report.sources) == 1


def test_get_source_provenance_node_id_is_idempotent():

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="test",
        )
    )

    context = (

        ResearchWorkspaceProjectionContext(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,

            provenance=collector,
        )
    )

    context.get_readiness()

    node_id = (

        context.get_source_provenance_node_id(
            "workspace.readiness"
        )
    )

    report = collector.build_report()

    assert (

        report.sources[0].node_id

        == node_id
    )


# ---------------------------------------------------------------------------
# Attention projector integration
# ---------------------------------------------------------------------------


def test_degraded_readiness_produces_provenance_derivation():

    projector = create_attention_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .DEGRADED,

            warnings=["Something is off"],
        ),
    )

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    projector.project(provenance=collector)

    report = collector.build_report()

    assert (

        [d.rule_name for d in report.derivations]

        == ["attention.readiness_degraded_rule"]
    )

    output_id = (

        collector.get_output_node_id(

            output_type="attention_item",

            output_key="readiness:degraded",
        )
    )

    source_ancestors = (

        report.get_source_ancestors(
            output_id
        )
    )

    assert (

        [s.source_name for s in source_ancestors]

        == ["workspace.readiness"]
    )


def test_unavailable_readiness_produces_provenance_derivation():

    projector = create_attention_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .UNAVAILABLE,

            blocking_reasons=["Core workspace down"],
        ),
    )

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    projector.project(provenance=collector)

    report = collector.build_report()

    assert (

        [d.rule_name for d in report.derivations]

        == ["attention.readiness_unavailable_rule"]
    )


def test_integrity_finding_produces_provenance_derivation():

    integrity_report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="broken_lineage_reference",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message="broken ref",

                    entity_type="research_session",

                    entity_id="session-842",
                ),
            ],
        )
    )

    projector = create_attention_projector(
        integrity_report=integrity_report,
    )

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    projector.project(provenance=collector)

    report = collector.build_report()

    assert (

        [d.rule_name for d in report.derivations]

        == ["attention.integrity_review_rule"]
    )

    output_id = (

        collector.get_output_node_id(

            output_type="attention_item",

            output_key=(
                "integrity:broken_lineage_reference:"
                "session-842"
            ),
        )
    )

    assert output_id is not None


def test_stale_paused_session_produces_provenance_derivation():

    projector = create_attention_projector(
        dormant_sessions=[dormant_summary()],
    )

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    projector.project(provenance=collector)

    report = collector.build_report()

    assert (

        [d.rule_name for d in report.derivations]

        == ["attention.stale_paused_session_rule"]
    )


def test_healthy_workspace_registers_sources_but_no_derivations():

    projector = create_attention_projector()

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    projection = (
        projector.project(provenance=collector)
    )

    assert projection.total_count == 0

    report = collector.build_report()

    assert report.derivations == []

    assert report.outputs == []

    assert report.edges == []

    assert len(report.sources) == 3


def test_project_without_provenance_is_safe_default():

    projector = create_attention_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .DEGRADED,

            warnings=["Something is off"],
        ),
    )

    projection = projector.project()

    assert projection.total_count == 1


def test_multiple_integrity_findings_share_one_source_node():

    integrity_report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="broken_lineage_reference",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message="broken ref one",

                    entity_type="research_session",

                    entity_id="session-1",
                ),

                ResearchIntegrityFinding(

                    code="orphaned_artifact",

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message="orphan",

                    entity_type="artifact",

                    entity_id="artifact-1",
                ),
            ],
        )
    )

    projector = create_attention_projector(
        integrity_report=integrity_report,
    )

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    projector.project(provenance=collector)

    report = collector.build_report()

    integrity_sources = [

        s

        for s in report.sources

        if s.source_name == "workspace.integrity"
    ]

    assert len(integrity_sources) == 1

    assert len(report.derivations) == 2

    assert len(report.outputs) == 2


def test_duplicate_attention_ids_do_not_double_register_provenance_output():

    integrity_report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="broken_lineage_reference",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message="first",

                    entity_type="research_session",

                    entity_id="session-1",
                ),

                ResearchIntegrityFinding(

                    code="broken_lineage_reference",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message="duplicate of first",

                    entity_type="research_session",

                    entity_id="session-1",
                ),
            ],
        )
    )

    projector = create_attention_projector(
        integrity_report=integrity_report,
    )

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.attention",
        )
    )

    projection = (
        projector.project(provenance=collector)
    )

    assert projection.total_count == 1

    report = collector.build_report()

    assert len(report.outputs) == 1

    assert len(report.derivations) == 1


# ---------------------------------------------------------------------------
# Bootstrap projector integration
# ---------------------------------------------------------------------------


def test_bootstrap_shares_provenance_collector_with_nested_attention():

    context_factory = (

        ResearchWorkspaceProjectionContextFactory(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .DEGRADED,

                        warnings=["Something is off"],
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,
        )
    )

    attention_projector = (

        ResearchWorkspaceAttentionProjector(
            context_factory=context_factory,
        )
    )

    bootstrap_projector = (

        ResearchWorkspaceBootstrapProjector(

            context_factory=context_factory,

            discovery_service=None,

            activity_service=None,

            attention_projector=attention_projector,

            action_projector=None,
        )
    )

    collector = (

        ResearchWorkspaceConsumerProjectionProvenanceCollector(
            operation_name="workspace.bootstrap",
        )
    )

    bootstrap_projector.project(

        provenance=collector,

        recent_session_limit=0,

        recent_activity_limit=0,
    )

    report = collector.build_report()

    assert (

        [d.rule_name for d in report.derivations]

        == ["attention.readiness_degraded_rule"]
    )

    readiness_sources = [

        s

        for s in report.sources

        if s.source_name == "workspace.readiness"
    ]

    assert len(readiness_sources) == 1


def test_bootstrap_without_provenance_is_safe_default():

    context_factory = (

        ResearchWorkspaceProjectionContextFactory(

            capability_registry=(
                FakeCapabilityRegistry()
            ),

            readiness_assessor=(

                FakeReadinessAssessor(

                    make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(
                FakeIntegrityAuditor()
            ),

            insights_service=(
                FakeInsightsService()
            ),

            session_manager=None,

            profile_store=None,
        )
    )

    attention_projector = (

        ResearchWorkspaceAttentionProjector(
            context_factory=context_factory,
        )
    )

    bootstrap_projector = (

        ResearchWorkspaceBootstrapProjector(

            context_factory=context_factory,

            discovery_service=None,

            activity_service=None,

            attention_projector=attention_projector,

            action_projector=None,
        )
    )

    projection = (

        bootstrap_projector.project(

            recent_session_limit=0,

            recent_activity_limit=0,
        )
    )

    assert projection.attention.total_count == 0


# ---------------------------------------------------------------------------
# Gateway integration (real application wiring)
# ---------------------------------------------------------------------------


def test_diagnose_bootstrap_returns_finalized_provenance_report():

    app = PreReqAIApplication()

    app.research_workspace.create_session(

        "session-1",

        paper_title="Attention Is All You Need",
    )

    result = (
        app.research_workspace.diagnose_bootstrap()
    )

    assert (

        result.provenance.operation_name

        == "workspace.bootstrap"
    )

    assert (

        {s.source_name for s in result.provenance.sources}

        >= {
            "workspace.capabilities",

            "workspace.readiness",

            "workspace.insights",
        }
    )


def test_diagnose_attention_returns_finalized_provenance_report():

    app = PreReqAIApplication()

    app.research_workspace.create_session(

        "session-1",

        paper_title="Attention Is All You Need",
    )

    result = (
        app.research_workspace.diagnose_attention()
    )

    assert (

        result.provenance.operation_name

        == "workspace.attention"
    )


def test_diagnose_bootstrap_provenance_is_independent_across_calls():

    app = PreReqAIApplication()

    app.research_workspace.create_session(

        "session-1",

        paper_title="Attention Is All You Need",
    )

    first = (
        app.research_workspace.diagnose_bootstrap()
    )

    second = (
        app.research_workspace.diagnose_bootstrap()
    )

    assert (

        first.provenance

        is not second.provenance
    )


def test_normal_bootstrap_contract_remains_unchanged():

    app = PreReqAIApplication()

    app.research_workspace.create_session(

        "session-1",

        paper_title="Attention Is All You Need",
    )

    projection = (
        app.research_workspace.get_bootstrap()
    )

    assert (

        not hasattr(
            projection,

            "provenance",
        )
    )


def test_diagnose_attention_still_produces_correct_projection_alongside_provenance():

    app = PreReqAIApplication()

    app.research_workspace.create_session(

        "session-1",

        paper_title="Attention Is All You Need",
    )

    result = (
        app.research_workspace.diagnose_attention()
    )

    assert (

        result.projection.total_count

        == len(result.projection.items)
    )
