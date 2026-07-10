from backend.interaction import (
    InteractionHistory,
    ObjectAction,
)


def test_interaction_history():

    history = (
        InteractionHistory()
    )

    history.record(
        "attention",
        "Attention",
        ObjectAction.EXPLAIN,
    )

    assert (
        len(history.events)
        == 1
    )

    assert (
        history.events[0].action
        == ObjectAction.EXPLAIN
    )


def test_interaction_history_has_completed():

    history = (
        InteractionHistory()
    )

    history.record(
        "attention",
        "Attention",
        ObjectAction.EXPLAIN,
    )

    assert history.has_completed(
        "attention",
        ObjectAction.EXPLAIN,
    )

    assert not history.has_completed(
        "attention",
        ObjectAction.QUIZ,
    )

    assert not history.has_completed(
        "eq3",
        ObjectAction.EXPLAIN,
    )


def test_interaction_history_recent_respects_limit():

    history = (
        InteractionHistory()
    )

    for _ in range(25):

        history.record(
            "attention",
            "Attention",
            ObjectAction.EXPLAIN,
        )

    assert len(history.recent()) == 20

    assert len(history.recent(limit=5)) == 5
