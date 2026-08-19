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
  response = client.get("/destinations/suggest")
  assert response.status_code == 401

  response = client.get("/destinations/suggest", headers={"X-App-Token": "dev-app-token"})
  assert response.status_code == 422


def test_options_preflight_is_not_blocked_by_app_token():
  response = client.options(
    "/destinations/suggest",
    headers={
      "Origin": "http://localhost:5173",
      "Access-Control-Request-Method": "GET",
      "Access-Control-Request-Headers": "x-app-token",
    },
  )
  assert response.status_code in {200, 204}
