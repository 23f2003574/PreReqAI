from backend.session import (
    JsonResearchSessionProfileStore,
    ResearchSessionProfile,
    ResearchSessionStatus,
)


def test_session_profile_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "session_profiles.json"
    )

    first_store = (

        JsonResearchSessionProfileStore(

            path
        )
    )

    first_store.save(

        ResearchSessionProfile(

            session_id=(
                "session-a"
            ),

            display_name=(
                "Mathematical Approach"
            ),

            status=(

                ResearchSessionStatus
                .PAUSED
            ),
        )
    )

    second_store = (

        JsonResearchSessionProfileStore(

            path
        )
    )

    restored = (

        second_store.get(

            "session-a"
        )
    )

    assert restored is not None

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
