from backend.session import (
    ResearchSessionProfile,
    ResearchSessionStatus,
)


def test_session_profile_round_trip():

    profile = (

        ResearchSessionProfile(

            session_id=(
                "session-a"
            ),

            display_name=(
                "Mathematical Approach"
            ),

            description=(
                "Explore theorem-first reasoning."
            ),

            status=(

                ResearchSessionStatus
                .PAUSED
            ),

            archived=True,

            metadata={

                "favorite":
                    True,
            },
        )
    )

    restored = (

        ResearchSessionProfile
        .from_dict(

            profile.to_dict()
        )
    )

    assert (

        restored.session_id

        == "session-a"
    )

    assert (

        restored.display_name

        == "Mathematical Approach"
    )

    assert (

        restored.status

        == (
            ResearchSessionStatus
            .PAUSED
        )
    )

    assert restored.archived is True


def test_session_profile_normalizes_empty_human_text():

    profile = (

        ResearchSessionProfile(

            session_id=(
                "session-a"
            ),

            display_name="   ",

            description="   ",
        )
    )

    assert (

        profile.display_name

        is None
    )

    assert (

        profile.description

        is None
    )
