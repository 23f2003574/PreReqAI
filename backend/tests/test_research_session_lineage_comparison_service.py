from types import SimpleNamespace

import pytest

from backend.session import (
    InMemoryResearchSessionBranchStore,
    ResearchSessionBranch,
    ResearchSessionLineageComparisonService,
    ResearchSessionLineageService,
    ResearchSessionSnapshot,
)

from frontend.src.app import (
    PreReqAIApplication,
)


class _FakeSessionManager:

    def __init__(

        self,

        session_ids,

    ):

        self._session_ids = set(
            session_ids
        )

    def load_session(

        self,

        session_id,

    ):

        if (

            session_id

            not in self._session_ids
        ):

            return None

        return ResearchSessionSnapshot(

            session_id=session_id
        )


def create_comparison_service():

    branch_store = (
        InMemoryResearchSessionBranchStore()
    )

    relationships = [

        (
            "A",
            "B",
            "checkpoint-ab",
            "version-ab",
        ),

        (
            "A",
            "C",
            "checkpoint-ac",
            "version-ac",
        ),

        (
            "B",
            "D",
            "checkpoint-bd",
            "version-bd",
        ),

        (
            "C",
            "E",
            "checkpoint-ce",
            "version-ce",
        ),
    ]

    for (

        parent,

        child,

        checkpoint,

        version,

    ) in relationships:

        branch_store.save(

            ResearchSessionBranch(

                source_session_id=(
                    parent
                ),

                source_checkpoint_id=(
                    checkpoint
                ),

                source_version_id=(
                    version
                ),

                branch_session_id=(
                    child
                ),
            )
        )

    lineage_service = (

        ResearchSessionLineageService(

            branch_store=branch_store
        )
    )

    session_manager = (

        _FakeSessionManager(

            {

                "A",

                "B",

                "C",

                "D",

                "E",

                "X",
            }
        )
    )

    return (

        ResearchSessionLineageComparisonService(

            session_manager=(
                session_manager
            ),

            branch_store=branch_store,

            lineage_service=(
                lineage_service
            ),

            artifact_store=None,
        )
    )


def test_comparison_detects_same_session():

    service = create_comparison_service()

    comparison = service.compare(
        "A",
        "A",
    )

    assert (

        comparison.relationship.value

        == "same"
    )

    assert comparison.lineage_distance == 0


def test_comparison_detects_ancestor_relationship():

    service = create_comparison_service()

    comparison = service.compare(
        "A",
        "D",
    )

    assert (

        comparison.relationship.value

        == "ancestor"
    )

    assert comparison.lineage_distance == 2


def test_comparison_detects_descendant_relationship():

    service = create_comparison_service()

    comparison = service.compare(
        "D",
        "A",
    )

    assert (

        comparison.relationship.value

        == "descendant"
    )

    assert comparison.lineage_distance == 2


def test_comparison_detects_siblings():

    service = create_comparison_service()

    comparison = service.compare(
        "B",
        "C",
    )

    assert (

        comparison.relationship.value

        == "sibling"
    )

    assert (

        comparison
        .common_ancestor_session_id

        == "A"
    )

    assert comparison.lineage_distance == 2


def test_comparison_detects_related_non_sibling_branches():

    service = create_comparison_service()

    comparison = service.compare(
        "D",
        "E",
    )

    assert (

        comparison.relationship.value

        == "cousin"
    )

    assert (

        comparison
        .common_ancestor_session_id

        == "A"
    )

    assert comparison.lineage_distance == 4


def test_comparison_detects_unrelated_sessions():

    service = create_comparison_service()

    comparison = service.compare(
        "D",
        "X",
    )

    assert (

        comparison.relationship.value

        == "unrelated"
    )

    assert comparison.related is False

    assert (

        comparison
        .common_ancestor_session_id

        is None
    )

    assert (

        comparison.lineage_distance

        is None
    )


def test_comparison_describes_lineage_divergence():

    service = create_comparison_service()

    comparison = service.compare(
        "D",
        "E",
    )

    divergence = (
        comparison.divergence
    )

    assert (

        divergence
        .common_ancestor_session_id

        == "A"
    )

    assert (

        divergence
        .first_path_from_common_ancestor

        == [
            "A",
            "B",
            "D",
        ]
    )

    assert (

        divergence
        .second_path_from_common_ancestor

        == [
            "A",
            "C",
            "E",
        ]
    )

    assert (

        divergence
        .first_divergent_session_id

        == "B"
    )

    assert (

        divergence
        .second_divergent_session_id

        == "C"
    )


def test_comparison_exposes_branch_origin_context():

    service = create_comparison_service()

    comparison = service.compare(
        "D",
        "E",
    )

    divergence = (
        comparison.divergence
    )

    assert (

        divergence
        .first_branch_checkpoint_id

        == "checkpoint-ab"
    )

    assert (

        divergence
        .first_branch_version_id

        == "version-ab"
    )

    assert (

        divergence
        .second_branch_checkpoint_id

        == "checkpoint-ac"
    )

    assert (

        divergence
        .second_branch_version_id

        == "version-ac"
    )


def test_ancestor_comparison_has_one_sided_divergence():

    service = create_comparison_service()

    comparison = service.compare(
        "A",
        "D",
    )

    divergence = (
        comparison.divergence
    )

    assert (

        divergence
        .first_path_from_common_ancestor

        == [
            "A",
        ]
    )

    assert (

        divergence
        .second_path_from_common_ancestor

        == [
            "A",
            "B",
            "D",
        ]
    )

    assert (

        divergence
        .first_divergent_session_id

        is None
    )

    assert (

        divergence
        .second_divergent_session_id

        == "B"
    )


def test_compares_identifier_collections():

    service = create_comparison_service()

    difference = (

        service._compare_ids(

            [
                "a",
                "b",
                "c",
            ],

            [
                "b",
                "c",
                "d",
            ],
        )
    )

    assert difference.shared_ids == [
        "b",
        "c",
    ]

    assert difference.first_only_ids == [
        "a",
    ]

    assert difference.second_only_ids == [
        "d",
    ]


def test_application_compares_real_research_branches():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    root_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "root-step"
        )
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "session-math"
        ),

        display_name=(
            "Mathematical Approach"
        ),
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "session-implementation"
        ),

        display_name=(
            "Implementation Approach"
        ),
    )

    comparison = (

        application
        .compare_research_sessions(

            "session-math",

            "session-implementation",
        )
    )

    assert (

        comparison.relationship.value

        == "sibling"
    )

    assert (

        comparison
        .common_ancestor_session_id

        == "session-main"
    )

    assert comparison.lineage_distance == 2

    assert (

        comparison
        .divergence
        .first_divergent_session_id

        == "session-math"
    )

    assert (

        comparison
        .divergence
        .second_divergent_session_id

        == "session-implementation"
    )


def test_application_compares_workflow_step_differences():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    root_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "root-step"
        )
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "session-math"
        ),
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "session-implementation"
        ),
    )

    application.restore_research_session(

        "session-math"
    )

    application.workspace.workspace.load_workflow_timeline(

        [
            SimpleNamespace(

                id="derive-linear-algebra",

                title=(
                    "Derive Linear Algebra"
                ),
            ),
        ]
    )

    application.save_research_session(

        "session-math"
    )

    application.restore_research_session(

        "session-implementation"
    )

    application.workspace.workspace.load_workflow_timeline(

        [
            SimpleNamespace(

                id="build-attention-layer",

                title=(
                    "Build Attention Layer"
                ),
            ),
        ]
    )

    application.save_research_session(

        "session-implementation"
    )

    comparison = (

        application
        .compare_research_sessions(

            "session-math",

            "session-implementation",
        )
    )

    assert (

        comparison.workflow_steps
        .first_only_ids

        == [
            "derive-linear-algebra",
        ]
    )

    assert (

        comparison.workflow_steps
        .second_only_ids

        == [
            "build-attention-layer",
        ]
    )

    assert (

        comparison.workflow_steps
        .shared_ids

        == []
    )


def test_application_compares_artifact_differences():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    root_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "root-step"
        )
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "session-math"
        ),
    )

    application.branch_research_checkpoint(

        root_checkpoint.id,

        branch_session_id=(
            "session-implementation"
        ),
    )

    math_artifact = (

        application
        .save_learning_artifact(

            session_id=(
                "session-math"
            ),

            object_id="attention",

            action="explain",

            content=(
                "Mathematical derivation"
            ),
        )
    )

    implementation_artifact = (

        application
        .save_learning_artifact(

            session_id=(
                "session-implementation"
            ),

            object_id="attention",

            action="implement",

            content=(
                "Reference implementation"
            ),
        )
    )

    comparison = (

        application
        .compare_research_sessions(

            "session-math",

            "session-implementation",
        )
    )

    assert (

        comparison.artifacts
        .first_only_ids

        == [
            math_artifact.id,
        ]
    )

    assert (

        comparison.artifacts
        .second_only_ids

        == [
            implementation_artifact.id,
        ]
    )

    assert (

        comparison.artifacts
        .shared_ids

        == []
    )


def test_comparison_rejects_missing_session():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    with pytest.raises(

        ValueError,

        match="does not exist",
    ):

        application.compare_research_sessions(

            "session-a",

            "missing-session",
        )
