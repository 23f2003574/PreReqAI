from backend.session import (
    JsonResearchSessionBranchStore,
    ResearchSessionBranch,
)


def test_session_branch_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "session_branches.json"
    )

    first_store = (

        JsonResearchSessionBranchStore(

            path
        )
    )

    branch = ResearchSessionBranch(

        source_session_id=(
            "session-main"
        ),

        source_checkpoint_id=(
            "checkpoint-1"
        ),

        source_version_id=(
            "version-1"
        ),

        branch_session_id=(
            "session-branch"
        ),
    )

    first_store.save(
        branch
    )

    second_store = (

        JsonResearchSessionBranchStore(

            path
        )
    )

    restored = (

        second_store
        .get_by_branch_session(

            "session-branch"
        )
    )

    assert restored is not None

    assert restored.id == branch.id

    assert (

        restored.source_session_id

        == "session-main"
    )
