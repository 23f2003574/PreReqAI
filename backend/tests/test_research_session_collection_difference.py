from backend.session import (
    ResearchSessionCollectionDifference,
)


def test_collection_difference_reports_counts():

    difference = (

        ResearchSessionCollectionDifference(

            shared_ids=[
                "a",
            ],

            first_only_ids=[
                "b",
                "c",
            ],

            second_only_ids=[
                "d",
            ],
        )
    )

    assert difference.shared_count == 1

    assert difference.first_only_count == 2

    assert difference.second_only_count == 1

    assert difference.differs is True


def test_collection_difference_detects_equivalent_sets():

    difference = (

        ResearchSessionCollectionDifference(

            shared_ids=[
                "a",
                "b",
            ]
        )
    )

    assert difference.differs is False
