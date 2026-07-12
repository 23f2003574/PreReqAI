import pytest

from backend.session import (

    JsonResearchSessionVersionStore,

    ResearchSessionSnapshot,

    ResearchSessionVersion,
)


def test_session_version_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "session_versions.json"
    )

    first_store = (

        JsonResearchSessionVersionStore(

            path
        )
    )

    version = ResearchSessionVersion(

        session_id="session-1",

        snapshot=(

            ResearchSessionSnapshot(

                session_id="session-1",

                paper_title=(
                    "Historical Paper"
                ),
            )
        ),
    )

    first_store.save(
        version
    )

    second_store = (

        JsonResearchSessionVersionStore(

            path
        )
    )

    restored = (

        second_store.get(

            version.id
        )
    )

    assert restored is not None

    assert (

        restored.snapshot
        .paper_title

        == "Historical Paper"
    )


def test_json_store_rejects_version_overwrite(

    tmp_path,

):

    store = (

        JsonResearchSessionVersionStore(

            tmp_path

            / "session_versions.json"
        )
    )

    version = ResearchSessionVersion(

        session_id="session-1",

        snapshot=(

            ResearchSessionSnapshot(

                session_id="session-1"
            )
        ),
    )

    store.save(
        version
    )

    with pytest.raises(
        ValueError
    ):

        store.save(
            version
        )
