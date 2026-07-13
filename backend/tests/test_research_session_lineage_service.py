import pytest

from backend.session import (
    InMemoryResearchSessionBranchStore,
    ResearchSessionBranch,
    ResearchSessionLineageService,
)


def create_lineage():

    store = (
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
            "B",
            "E",
            "checkpoint-be",
            "version-be",
        ),

        (
            "X",
            "Y",
            "checkpoint-xy",
            "version-xy",
        ),
    ]

    for (

        parent,

        child,

        checkpoint,

        version,

    ) in relationships:

        store.save(

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

    service = (

        ResearchSessionLineageService(

            branch_store=store
        )
    )

    return service


def test_resolves_parent_and_children():

    service = create_lineage()

    assert (

        service.parent_session_id(
            "D"
        )

        == "B"
    )

    assert (

        service.parent_session_id(
            "A"
        )

        is None
    )

    assert set(

        service.child_session_ids(
            "A"
        )

    ) == {

        "B",
        "C",
    }


def test_lists_ancestors_nearest_first():

    service = create_lineage()

    assert (

        service.ancestor_session_ids(
            "D"
        )

        == [
            "B",
            "A",
        ]
    )


def test_resolves_root_and_depth():

    service = create_lineage()

    assert (

        service.root_session_id(
            "D"
        )

        == "A"
    )

    assert (

        service.depth(
            "A"
        )

        == 0
    )

    assert (

        service.depth(
            "B"
        )

        == 1
    )

    assert (

        service.depth(
            "D"
        )

        == 2
    )


def test_lists_descendants_breadth_first():

    service = create_lineage()

    assert (

        service.descendant_session_ids(
            "A"
        )

        == [
            "B",
            "C",
            "D",
            "E",
        ]
    )


def test_builds_path_from_root():

    service = create_lineage()

    path = (

        service.path_from_root(
            "D"
        )
    )

    assert (

        path.session_ids

        == [
            "A",
            "B",
            "D",
        ]
    )

    assert path.edge_count == 2


def test_detects_related_sessions():

    service = create_lineage()

    assert (

        service.are_related(

            "D",

            "C",
        )

        is True
    )

    assert (

        service.are_related(

            "D",

            "Y",
        )

        is False
    )


def test_detects_ancestor_relationship():

    service = create_lineage()

    assert (

        service.is_ancestor(

            "A",

            "D",
        )

        is True
    )

    assert (

        service.is_ancestor(

            "C",

            "D",
        )

        is False
    )


def test_finds_lowest_common_ancestor():

    service = create_lineage()

    assert (

        service.lowest_common_ancestor(

            "D",

            "E",
        )

        == "B"
    )

    assert (

        service.lowest_common_ancestor(

            "D",

            "C",
        )

        == "A"
    )

    assert (

        service.lowest_common_ancestor(

            "D",

            "Y",
        )

        is None
    )


def test_builds_path_between_related_sessions():

    service = create_lineage()

    path = (

        service.path_between(

            "D",

            "C",
        )
    )

    assert path is not None

    assert (

        path.session_ids

        == [
            "D",
            "B",
            "A",
            "C",
        ]
    )


def test_returns_none_for_path_between_unrelated_sessions():

    service = create_lineage()

    assert (

        service.path_between(

            "D",

            "Y",
        )

        is None
    )


def test_builds_nested_lineage_tree():

    service = create_lineage()

    tree = (

        service.lineage_tree(
            "D"
        )
    )

    assert tree.session_id == "A"

    assert tree.depth == 0

    assert {

        child.session_id

        for child

        in tree.children

    } == {

        "B",
        "C",
    }

    branch_b = next(

        child

        for child

        in tree.children

        if child.session_id == "B"
    )

    assert branch_b.depth == 1

    assert {

        child.session_id

        for child

        in branch_b.children

    } == {

        "D",
        "E",
    }


def test_summarizes_session_lineage():

    service = create_lineage()

    summary = (

        service.summarize(
            "B"
        )
    )

    assert (

        summary.root_session_id

        == "A"
    )

    assert (

        summary.parent_session_id

        == "A"
    )

    assert summary.depth == 1

    assert summary.ancestor_count == 1

    assert summary.child_count == 2

    assert summary.descendant_count == 2


def test_detects_cycle_during_ancestor_traversal():

    store = (
        InMemoryResearchSessionBranchStore()
    )

    for parent, child in [

        ("A", "B"),

        ("B", "C"),

        ("C", "A"),
    ]:

        store.save(

            ResearchSessionBranch(

                source_session_id=(
                    parent
                ),

                source_checkpoint_id=(

                    f"checkpoint-"
                    f"{parent}-{child}"
                ),

                source_version_id=(

                    f"version-"
                    f"{parent}-{child}"
                ),

                branch_session_id=(
                    child
                ),
            )
        )

    service = (

        ResearchSessionLineageService(

            branch_store=store
        )
    )

    with pytest.raises(

        ValueError,

        match="Cycle detected",
    ):

        service.ancestor_session_ids(
            "A"
        )
