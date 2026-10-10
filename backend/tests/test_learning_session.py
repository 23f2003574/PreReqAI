from backend.session import (
    SessionManager,
)


def test_session_creation():

    manager = SessionManager()

    session = manager.create(
        "Attention Is All You Need",
    )

    assert session.status == "active"

    assert session.paper_title == (
        "Attention Is All You Need"
    )


def test_session_stores_report_for_lookup():

    manager = SessionManager()

    session = manager.create(
        paper_title="Attention Is All You Need",
        report={
            "prerequisite_justifications": [
                {
                    "concept": "Linear Algebra",
                    "justification": "Used in matrix multiplications.",
                },
            ],
        },
    )

    fetched = manager.get(session.session_id)

    assert fetched is session

    assert fetched.report[
        "prerequisite_justifications"
    ][0]["concept"] == "Linear Algebra"
