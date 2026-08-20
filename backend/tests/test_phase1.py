import json

from app.constants import STATIC_INTERESTS
from app.db.models import TripState
from app.services.geoapify import _result_to_place, categories_for_interests
from app.services.interests import (
    format_interest_label,
    interest_sentence,
    interests_for_destination,
    unique_interest_tags,
)
from app.services.itinerary import (
    _chunk_windows,
    _day_count,
    _day_dates,
    _dedupe_days,
    _extract_json,
    _stitch_days,
    trip_is_complete,
)


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
    assert _day_count({"start": "2026-08-17", "end": "2026-08-21"}) == 5
    assert _day_count({"start": "2026-08-17", "end": "2026-08-23"}) == 7
    assert _day_count({"start": "2026-08-01", "end": "2026-08-14"}) == 14
    assert _day_count({"start": "2026-08-01", "end": "2026-08-20"}) == 14


def test_chunk_windows_split_into_three_day_batches():
    assert _chunk_windows(1) == [(0, 1)]
    assert _chunk_windows(3) == [(0, 3)]
    assert _chunk_windows(7) == [(0, 3), (3, 6), (6, 7)]
    assert _chunk_windows(14) == [(0, 3), (3, 6), (6, 9), (9, 12), (12, 14)]


def test_day_dates_fill_iso_for_each_day():
    assert _day_dates(None) == [None, None, None]
    assert _day_dates({"start": "2026-08-17", "end": "2026-08-21"}) == [
        "2026-08-17",
        "2026-08-18",
        "2026-08-19",
        "2026-08-20",
        "2026-08-21",
    ]


def test_dedupe_and_stitch_drop_repeated_places():
    first = [
        {
            "day": 1,
            "activities": [{"title": "Louvre", "location": "Louvre"}],
            "meals": [{"type": "Lunch", "venue": "Le Comptoir"}],
        }
    ]
    second = [
        {
            "day": 1,
            "activities": [
                {"title": "Louvre again", "location": "The Louvre"},
                {"title": "Marais walk", "location": "Le Marais"},
            ],
            "meals": [{"type": "Lunch", "venue": "Le Comptoir"}],
        }
    ]
    used: set[str] = set()
    labels: list[str] = []
    kept = _dedupe_days(first, used, labels)
    kept.extend(_dedupe_days(second, used, labels))
    stitched = _stitch_days(kept, ["2026-08-17", "2026-08-18"])
    places = [
        act["location"]
        for day in stitched["days"]
        for act in day["activities"]
    ]
    venues = [meal["venue"] for day in stitched["days"] for meal in day["meals"]]
    assert [day["day"] for day in stitched["days"]] == [1, 2]
    assert stitched["days"][1]["dayLabel"] == "Day 2"
    assert stitched["days"][1]["date"] == "2026-08-18"
    assert places == ["Louvre", "Le Marais"]
    assert venues == ["Le Comptoir"]
    assert "The Louvre" not in places


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
