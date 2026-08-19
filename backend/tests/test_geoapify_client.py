from unittest.mock import patch

from app.services.geoapify import autocomplete_cities


def test_autocomplete_cities_uses_geoapify_json_results():
    payload = {
        "results": [
            {
                "city": "Tokyo",
                "formatted": "Tokyo, Japan",
                "country": "Japan",
                "place_id": "tok",
                "lat": 35.6,
                "lon": 139.7,
            }
        ]
    }
    mock_response = type("Resp", (), {"is_error": False, "json": lambda self: payload})()
    with (
        patch("app.services.geoapify._require_key", return_value="test-key"),
        patch("app.services.geoapify.httpx.get", return_value=mock_response),
    ):
        places = autocomplete_cities("tok")
    assert places[0]["name"] == "Tokyo"
    assert places[0]["place_id"] == "tok"
