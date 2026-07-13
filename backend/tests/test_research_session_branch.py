from backend.session import (
    ResearchSessionBranch,
)


def test_session_branch_round_trip():

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

        metadata={

            "label":
                "Alternative approach",
        },
    )

    restored = (

        ResearchSessionBranch
        .from_dict(

            branch.to_dict()
        )
    )

    assert restored.id == branch.id

    assert (

        restored.source_session_id

        == "session-main"
    )

    assert (

        restored.branch_session_id

        == "session-branch"
    )
