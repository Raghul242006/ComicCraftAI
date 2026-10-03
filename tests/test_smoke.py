from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_homepage():
    response = client.get("/")

    assert response.status_code == 200

    assert "ComicCraft" in response.text


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"