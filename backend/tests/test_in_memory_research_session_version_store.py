import pytest

from backend.session import (

    InMemoryResearchSessionVersionStore,

    ResearchSessionSnapshot,

    ResearchSessionVersion,
)


def test_rejects_overwriting_existing_version():

    store = (

        InMemoryResearchSessionVersionStore()
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

        ValueError,

        match=(

            "Research session version "
            "already exists"
        ),
    ):

        store.save(
            version
        )


def test_stored_version_isolated_from_original_snapshot():

    store = (

        InMemoryResearchSessionVersionStore()
    )

    snapshot = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Original Title",
    )

    version = ResearchSessionVersion(

        session_id="session-1",

        snapshot=snapshot,
    )

    store.save(
        version
    )

    snapshot.paper_title = (
        "Mutated Title"
    )

    restored = store.get(
        version.id
    )

    assert (

        restored.snapshot
        .paper_title

        == "Original Title"
    )
