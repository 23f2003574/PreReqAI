from backend.session import (

    InMemoryInteractionArtifactLinkStore,

    InteractionArtifactLink,
)


def test_saves_interaction_artifact_link():

    store = (

        InMemoryInteractionArtifactLinkStore()
    )

    link = InteractionArtifactLink(

        interaction_id="interaction-1",

        artifact_id="artifact-1",

        session_id="session-1",

        object_id="attention",

        action="explain",
    )

    store.save(
        link
    )

    links = (

        store.list_for_interaction(

            "interaction-1"
        )
    )

    assert len(links) == 1

    assert (

        links[0].artifact_id

        == "artifact-1"
    )


def test_does_not_duplicate_same_link():

    store = (

        InMemoryInteractionArtifactLinkStore()
    )

    link = InteractionArtifactLink(

        interaction_id="interaction-1",

        artifact_id="artifact-1",

        session_id="session-1",

        object_id="attention",

        action="explain",
    )

    store.save(link)

    store.save(link)

    links = (

        store.list_for_interaction(

            "interaction-1"
        )
    )

    assert len(links) == 1


def test_lists_links_for_session_and_artifact():

    store = (

        InMemoryInteractionArtifactLinkStore()
    )

    link = InteractionArtifactLink(

        interaction_id="interaction-1",

        artifact_id="artifact-1",

        session_id="session-1",

        object_id="attention",

        action="explain",
    )

    store.save(link)

    assert (

        len(
            store.list_for_session(
                "session-1"
            )
        )

        == 1
    )

    assert (

        len(
            store.list_for_artifact(
                "artifact-1"
            )
        )

        == 1
    )
