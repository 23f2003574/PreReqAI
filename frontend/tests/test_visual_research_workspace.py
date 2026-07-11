from dataclasses import dataclass

from frontend.src.workspace import (

    VisualResearchWorkspace,

    WorkspaceView,
)


@dataclass
class Section:

    id: str

    title: str

    level: int


def test_opens_research_paper():

    workspace = (
        VisualResearchWorkspace()
    )

    sections = [

        Section(

            id="introduction",

            title="Introduction",

            level=1,
        ),

        Section(

            id="architecture",

            title="Architecture",

            level=1,
        ),
    ]

    result = workspace.open_paper(

        "Example Research Paper",

        sections,
    )

    assert (

        result["outline"].paper_title

        == "Example Research Paper"
    )

    assert (

        len(
            result["outline"].roots
        )

        == 2
    )


def test_switches_workspace_view():

    workspace = (
        VisualResearchWorkspace()
    )

    active_view = (

        workspace.switch_view(

            WorkspaceView.KNOWLEDGE_GRAPH
        )
    )

    assert (

        active_view

        == "knowledge_graph"
    )


def test_creates_workspace_snapshot():

    workspace = (
        VisualResearchWorkspace()
    )

    sections = [

        Section(

            id="introduction",

            title="Introduction",

            level=1,
        ),
    ]

    workspace.open_paper(

        "Example Research Paper",

        sections,
    )

    snapshot = (
        workspace.snapshot()
    )

    assert (

        snapshot["active_view"]

        == "paper"
    )

    assert (

        len(
            snapshot["breadcrumbs"]
        )

        == 1
    )
