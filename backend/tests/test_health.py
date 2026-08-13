from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_200():
  response = client.get("/health")
  assert response.status_code == 200
  data = response.json()
  assert "status" in data
  assert "db" in data
  assert "redis" in data


def test_app_token_required_for_non_exempt_paths():
  response = client.get("/openapi.json")
  assert response.status_code == 401

  response = client.get("/openapi.json", headers={"X-App-Token": "dev-app-token"})
  assert response.status_code == 200
