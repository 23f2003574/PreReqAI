import pytest

from backend.session import (
    InMemoryResearchSessionBranchStore,
    ResearchSessionBranch,
)


def test_branch_session_can_have_only_one_origin():

    store = (
        InMemoryResearchSessionBranchStore()
    )

    first = ResearchSessionBranch(

        source_session_id="session-a",

        source_checkpoint_id=(
            "checkpoint-a"
        ),

        source_version_id="version-a",

        branch_session_id=(
            "session-child"
        ),
    )

    second = ResearchSessionBranch(

        source_session_id="session-b",

        source_checkpoint_id=(
            "checkpoint-b"
        ),

        source_version_id="version-b",

        branch_session_id=(
            "session-child"
        ),
    )

    store.save(
        first
    )

    with pytest.raises(

        ValueError,

        match=(
            "already has a branch origin"
        ),
    ):

        store.save(
            second
        )
