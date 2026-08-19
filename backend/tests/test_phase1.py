import json

from app.constants import STATIC_INTERESTS
from app.db.models import TripState
from app.services.geoapify import _result_to_place, categories_for_interests
from app.services.interests import (
    format_interest_label,
    interests_for_destination,
    unique_interest_tags,
)
from app.services.itinerary import _day_count, _extract_json, trip_is_complete


def test_categories_for_interests_maps_mock_tags():
    cats = categories_for_interests(["Street Food", "Nightlife"])
    assert "catering" in cats
    assert "catering.bar" in cats


def test_categories_default_when_empty():
    assert categories_for_interests([]) == "tourism,entertainment,catering"


def test_result_to_place_normalizes_geoapify_json():
    place = _result_to_place(
        {
            "city": "Paris",
            "formatted": "Paris, France",
            "country": "France",
            "place_id": "abc",
            "lat": 48.8,
            "lon": 2.3,
        }
    )
    assert place is not None
    assert place["name"] == "Paris"
    assert place["place_id"] == "abc"


def test_interest_labels_are_title_case_and_short():
    assert format_interest_label("street food") == "Street Food"
    assert format_interest_label("Museums & Art History") == "Museums Art"
    assert format_interest_label("  hidden   cafes ") == "Hidden Cafes"


def test_unique_interest_tags_drops_repeats():
    assert unique_interest_tags(["Street Food", "street food", "Street  Food"]) == ["Street Food"]


def test_interests_for_destination_filters_general_tags():
    paris = interests_for_destination("Paris, France")
    bali = interests_for_destination("Bali, Indonesia")
    machu = interests_for_destination("Machu Picchu, Peru")

    assert "Street Food" in paris
    assert "Cafes" in paris
    assert "Beaches" not in paris
    assert "Wildlife" not in paris

    assert "Beaches" in bali
    assert "Temples" in bali
    assert "Mountain Hikes" not in bali

    assert "Hiking" in machu
    assert "Ruins" in machu
    assert "Nightlife" not in machu
    assert "Beaches" not in machu

    for tags in (paris, bali, machu):
        assert len(tags) >= 8
        for common in ("Street Food", "Local Markets", "Cafes"):
            assert common in tags
        assert tags == unique_interest_tags(tags)
        for tag in tags:
            assert 1 <= len(tag.split()) <= 2
            assert tag == format_interest_label(tag)

    assert set(STATIC_INTERESTS) - set(paris)


def test_day_count_from_range_and_flexible():
    assert _day_count(None) == 3
    assert _day_count({"start": "2026-08-17", "end": "2026-08-19"}) == 3


def test_extract_json_accepts_markdown_and_trailing_comma():
    wrapped = """```json
    {"days": [{"day": 1, "items": []}],}
    ```"""
    parsed = _extract_json(wrapped)
    assert parsed["days"][0]["day"] == 1
    assert parsed["days"][0]["activities"] == []


def test_extract_json_limits_activities_and_drops_times():
    parsed = _extract_json(
        json.dumps(
            {
                "days": [
                    {
                        "day": 1,
                        "activities": [
                            {"time": "09:00", "title": "One"},
                            {"time": "11:00", "title": "Two"},
                            {"time": "13:00", "title": "Three"},
                            {"time": "16:00", "title": "Four"},
                        ],
                    }
                ]
            }
        )
    )
    activities = parsed["days"][0]["activities"]
    assert len(activities) == 3
    assert [row["title"] for row in activities] == ["One", "Two", "Three"]
    assert all("time" not in row for row in activities)


def test_trip_is_complete_requires_template_fields():
    trip = TripState(destination="Paris")
    assert trip_is_complete(trip) is False
    trip.trip_type = "Solo"
    assert trip_is_complete(trip) is False
    trip.flavor_preference = "Moderate"
    assert trip_is_complete(trip) is True
