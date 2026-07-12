from datetime import (
    datetime,
    timedelta,
)

import pytest

from backend.session import (
    ResearchCheckpointReason,
    ResearchHistoryQuery,
    ResearchHistorySortOrder,
)


def test_rejects_negative_history_offset():

    with pytest.raises(

        ValueError,

        match="cannot be negative",
    ):

        ResearchHistoryQuery(

            offset=-1
        )


def test_rejects_non_positive_history_limit():

    with pytest.raises(

        ValueError,

        match=(
            "must be greater than zero"
        ),
    ):

        ResearchHistoryQuery(

            limit=0
        )


def test_rejects_inverted_history_date_range():

    now = datetime.utcnow()

    with pytest.raises(

        ValueError,

        match=(
            "cannot be after"
        ),
    ):

        ResearchHistoryQuery(

            created_from=now,

            created_until=(

                now

                - timedelta(
                    days=1
                )
            ),
        )


def test_normalizes_string_reasons_to_enum_members():

    query = ResearchHistoryQuery(

        reasons={
            "artifact_created"
        }
    )

    assert (

        ResearchCheckpointReason
        .ARTIFACT_CREATED

        in query.reasons
    )


def test_normalizes_string_sort_order_to_enum():

    query = ResearchHistoryQuery(

        sort_order="oldest"
    )

    assert (

        query.sort_order

        == (
            ResearchHistorySortOrder
            .OLDEST
        )
    )
