"""Verify the API liveness endpoint contract."""

from fastapi.testclient import TestClient

from venuepass_api.main import app


# Reuse one in-process client because this module has only stateless requests.
client = TestClient(app)


def test_health() -> None:
    """Return a stable success response while the API process is healthy."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
