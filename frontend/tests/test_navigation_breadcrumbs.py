from frontend.src.navigation import (
    NavigationBreadcrumbs,
)


def test_builds_navigation_trail():

    breadcrumbs = (
        NavigationBreadcrumbs()
    )

    breadcrumbs.enter(

        id="paper",

        label="Example Paper",

        context_type="paper",
    )

    breadcrumbs.enter(

        id="architecture",

        label="Architecture",

        context_type="section",
    )

    breadcrumbs.enter(

        id="attention",

        label="Attention",

        context_type="concept",
    )

    items = breadcrumbs.items()

    assert (

        len(items)

        == 3
    )

    assert (

        items[-1].label

        == "Attention"
    )


def test_navigates_to_previous_context():

    breadcrumbs = (
        NavigationBreadcrumbs()
    )

    breadcrumbs.enter(

        id="paper",

        label="Example Paper",

        context_type="paper",
    )

    breadcrumbs.enter(

        id="attention",

        label="Attention",

        context_type="concept",
    )

    selected = (

        breadcrumbs.navigate_to(
            0
        )
    )

    assert (

        selected.context_type

        == "paper"
    )

    assert (

        len(
            breadcrumbs.items()
        )

        == 1
    )


def test_reentering_context_truncates_trail():

    breadcrumbs = (
        NavigationBreadcrumbs()
    )

    breadcrumbs.enter(

        id="paper",

        label="Example Paper",

        context_type="paper",
    )

    breadcrumbs.enter(

        id="attention",

        label="Attention",

        context_type="concept",
    )

    breadcrumbs.enter(

        id="equation-3",

        label="Equation (3)",

        context_type="equation",
    )

    breadcrumbs.enter(

        id="attention",

        label="Attention",

        context_type="concept",
    )

    assert (

        len(
            breadcrumbs.items()
        )

        == 2
    )
