import pytest

from backend.session import (
    ResearchSessionKind,
    ResearchSessionQuery,
    ResearchSessionStatus,
)


def test_rejects_negative_session_query_offset():

    with pytest.raises(

        ValueError,

        match="cannot be negative",
    ):

        ResearchSessionQuery(

            offset=-1
        )


def test_rejects_non_positive_session_query_limit():

    with pytest.raises(

        ValueError,

        match=(
            "must be greater than zero"
        ),
    ):

        ResearchSessionQuery(

            limit=0
        )


def test_normalizes_session_query_enum_values():

    query = (

        ResearchSessionQuery(

            statuses={
                "active",
                "paused",
            },

            kinds={
                "root",
            },

            sort_order=(
                "name_ascending"
            ),
        )
    )

    assert (

        ResearchSessionStatus
        .ACTIVE

        in query.statuses
    )

    assert (

        ResearchSessionStatus
        .PAUSED

        in query.statuses
    )

    assert (

        ResearchSessionKind
        .ROOT

        in query.kinds
    )
