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
  # /trip is not implemented yet (Phase 1), but it is not token-exempt.
  response = client.get("/trip")
  assert response.status_code == 401

  response = client.get("/trip", headers={"X-App-Token": "dev-app-token"})
  assert response.status_code == 404
