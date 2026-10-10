from dataclasses import dataclass

from backend.session import (

    ResearchRuntimeRegistry,

    ResearchRuntimeResolver,

    ResearchSessionRestorer,

    ResearchSessionSnapshot,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


@dataclass
class ResearchObject:

    id: str


def test_restores_selected_object():

    registry = (
        ResearchRuntimeRegistry()
    )

    research_object = (

        ResearchObject(

            id="attention"
        )
    )

    registry.register_object(

        research_object
    )

    resolver = (

        ResearchRuntimeResolver(

            registry
        )
    )

    restorer = (

        ResearchSessionRestorer(

            resolver
        )
    )

    snapshot = (

        ResearchSessionSnapshot(

            session_id="session-1",

            selected_object_id=(
                "attention"
            ),
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    result = restorer.restore(

        snapshot,

        workspace,
    )

    assert (

        result.restored_object

        is research_object
    )

    assert (

        workspace.state
        .selected_object

        is research_object
    )


def test_reports_unresolved_reference():

    registry = (
        ResearchRuntimeRegistry()
    )

    resolver = (

        ResearchRuntimeResolver(

            registry
        )
    )

    restorer = (

        ResearchSessionRestorer(

            resolver
        )
    )

    snapshot = (

        ResearchSessionSnapshot(

            session_id="session-1",

            selected_object_id=(
                "missing-object"
            ),
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    result = restorer.restore(

        snapshot,

        workspace,
    )

    assert (

        result.unresolved_references

        == [

            "research_object:"
            "missing-object"
        ]
    )


def test_restores_workflow_timeline():

    registry = (
        ResearchRuntimeRegistry()
    )

    resolver = (

        ResearchRuntimeResolver(

            registry
        )
    )

    restorer = (

        ResearchSessionRestorer(

            resolver
        )
    )

    snapshot = (

        ResearchSessionSnapshot(

            session_id="session-1",

            timeline=[

                {

                    "id": "step-1",

                    "title": "Explain",

                    "status":
                        "completed",
                },

                {

                    "id": "step-2",

                    "title": "Quiz",

                    "status":
                        "active",
                },
            ],
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    restorer.restore(

        snapshot,

        workspace,
    )

    steps = workspace.timeline()

    assert (

        len(steps)

        == 2
    )

    assert (

        workspace.workspace
        .learning_timeline
        .active_step_id

        == "step-2"
    )


def test_restores_breadcrumbs_and_recommendations():

    registry = (
        ResearchRuntimeRegistry()
    )

    resolver = (

        ResearchRuntimeResolver(

            registry
        )
    )

    restorer = (

        ResearchSessionRestorer(

            resolver
        )
    )

    snapshot = (

        ResearchSessionSnapshot(

            session_id="session-1",

            active_view=(
                "knowledge_graph"
            ),

            breadcrumbs=[

                {

                    "id": "paper",

                    "label":
                        "Example Paper",

                    "context_type":
                        "paper",
                },
            ],

            recommendations=[

                {

                    "id":
                        "recommendation-1",

                    "title":
                        "Explain Attention",

                    "description":
                        "Learn how attention works.",

                    "action":
                        "explain",

                    "object_id":
                        "attention",

                    "priority": 5,
                },
            ],
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    restorer.restore(

        snapshot,

        workspace,
    )

    assert (

        workspace.state.active_view

        == "knowledge_graph"
    )

    assert (

        len(
            workspace.breadcrumbs()
        )

        == 1
    )

    assert (

        len(
            workspace.recommendations()
        )

        == 1
    )
