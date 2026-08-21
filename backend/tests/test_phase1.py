import json

from app.constants import STATIC_INTERESTS
from app.db.models import TripState
from app.services.geoapify.map import (
    MAP_STYLE,
    map_area_rect,
    map_center,
    static_map_marker,
    static_map_request_body,
)
from app.services.geoapify.poi import _result_to_place, categories_for_interests
from app.services.interests import (
    format_interest_label,
    interest_sentence,
    interests_for_destination,
    unique_interest_tags,
)
from app.services.itinerary import _day_count, _extract_json, trip_is_complete


def test_categories_for_story_interest_codes():
    cats = categories_for_interests(["sights", "food_drink"])
    assert "tourism.sights" in cats
    assert "catering" in cats


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


def test_static_map_marker_format():
    marker = static_map_marker(2.3, 48.8, color="#333d29", text="1")
    assert marker["lon"] == 2.3
    assert marker["lat"] == 48.8
    assert marker["type"] == "circle"
    assert marker["color"] == "#333d29"
    assert marker["text"] == "1"
    assert marker["textsize"] == "medium"


def test_static_map_request_body_uses_post_customization():
    body = static_map_request_body([(2.35, 48.85), (2.13, 48.80)])
    assert body["style"] == MAP_STYLE
    assert body["format"] == "png"
    assert body["markers"][0]["text"] == "1"
    assert body["markers"][1]["color"] == "#c8a96e"
    assert "geometries" not in body
    assert "area" not in body
    assert "zoom" not in body
    assert body["center"]["lon"] == (2.35 + 2.13) / 2
    assert body["center"]["lat"] == (48.85 + 48.80) / 2


def test_map_center_is_midpoint():
    center = map_center([(2.35, 48.85), (2.34, 48.848)])
    assert 2.33 < center["lon"] < 2.36
    assert 48.848 <= center["lat"] <= 48.85


def test_map_area_rect_pads_bounds():
    area = map_area_rect([(2.3, 48.8), (2.4, 48.9)])
    assert area["type"] == "rect"
    value = area["value"]
    assert value["lon1"] < 2.3
    assert value["lon2"] > 2.4
    assert value["lon2"] - value["lon1"] < 0.2


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


def test_fine_dining_hidden_on_budget_friendly_and_moderate():
    luxury = interests_for_destination("Paris, France", "Luxury")
    comfortable = interests_for_destination("Paris, France", "Comfortable")
    modest = interests_for_destination("Paris, France", "Budget-friendly")
    moderate = interests_for_destination("Paris, France", "Moderate")
    assert "Fine Dining" in luxury
    assert "Fine Dining" in comfortable
    assert "Fine Dining" not in modest
    assert "Fine Dining" not in moderate
    assert len(modest) >= 8
    assert len(moderate) >= 8


def test_interest_sentence_names_every_selected_tag():
    sentence = interest_sentence("Paris, France", ["Street Food", "Museums", "Cafes"])
    assert sentence.startswith("This Paris plan")
    assert "street food" in sentence
    assert "museums" in sentence
    assert "cafes" in sentence
    assert sentence.count(".") == 1


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
