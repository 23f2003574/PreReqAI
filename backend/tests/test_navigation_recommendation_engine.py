from backend.navigation import (
    NavigationHistory,
    NavigationRecommendationEngine,
    NavigationTarget,
)


def test_navigation_recommendations():

    history = NavigationHistory()

    history.record(

        NavigationTarget.CONCEPT,

        "Attention",
    )

    engine = (

        NavigationRecommendationEngine()
    )

    recommendations = (

        engine.recommend(

            history,
        )
    )

    assert (

        NavigationTarget.EQUATION

        in recommendations
    )


def test_navigation_recommendations_empty_history():

    history = NavigationHistory()

    engine = NavigationRecommendationEngine()

    recommendations = engine.recommend(history)

    assert recommendations == [
        NavigationTarget.SECTION
    ]


def test_navigation_recommendations_unmapped_target_falls_back():

    history = NavigationHistory()

    history.record(
        NavigationTarget.SECTION,
        "Introduction",
    )

    engine = NavigationRecommendationEngine()

    recommendations = engine.recommend(history)

    assert recommendations == [
        NavigationTarget.CONCEPT
    ]
