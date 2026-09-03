from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "project" in response.json()

from src.infrastructure.database.connection import get_session

def test_database_connection_yields():
    generator = get_session()
    assert generator is not None
