from fastapi.testclient import (
    TestClient,
)

from backend.main import app


client = TestClient(app)


def test_prerequisite_endpoint_exists():

    response = client.post(
        "/api/prerequisites/analyze",
        files={
            "paper": (
                "sample.pdf",
                b"dummy",
                "application/pdf",
            )
        },
    )

    assert response.status_code != 404
