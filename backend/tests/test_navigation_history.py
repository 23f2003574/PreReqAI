from backend.navigation import (
    NavigationHistory,
    NavigationTarget,
)


def test_navigation_history():

    history = NavigationHistory()

    history.record(

        NavigationTarget.CONCEPT,

        "Attention",
    )

    assert (

        len(history.events)

        == 1
    )

    assert (

        history.events[0].title

        == "Attention"
    )


def test_navigation_history_recent_respects_limit():

    history = NavigationHistory()

    for i in range(15):

        history.record(
            NavigationTarget.SECTION,
            f"Section {i}",
        )

    recent = history.recent(limit=10)

    assert len(recent) == 10
    assert recent[0].title == "Section 5"
    assert recent[-1].title == "Section 14"
