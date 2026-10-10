from backend.session import (

    InteractionArtifactLink,

    JsonInteractionArtifactLinkStore,
)


def test_link_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "links.json"
    )

    first_store = (

        JsonInteractionArtifactLinkStore(

            path
        )
    )

    first_store.save(

        InteractionArtifactLink(

            interaction_id=(
                "interaction-1"
            ),

            artifact_id=(
                "artifact-1"
            ),

            session_id=(
                "session-1"
            ),

            object_id="attention",

            action="explain",
        )
    )

    second_store = (

        JsonInteractionArtifactLinkStore(

            path
        )
    )

    links = (

        second_store
        .list_for_interaction(

            "interaction-1"
        )
    )

    assert len(links) == 1

    assert (

        links[0].artifact_id

        == "artifact-1"
    )


def test_does_not_duplicate_same_link(

    tmp_path,

):

    path = (

        tmp_path

        / "links.json"
    )

    store = (

        JsonInteractionArtifactLinkStore(
            path
        )
    )

    link = InteractionArtifactLink(

        interaction_id=(
            "interaction-1"
        ),

        artifact_id="artifact-1",

        session_id="session-1",

        object_id="attention",

        action="explain",
    )

    store.save(link)

    store.save(link)

    assert (

        len(
            store.list_for_interaction(
                "interaction-1"
            )
        )

        == 1
    )
