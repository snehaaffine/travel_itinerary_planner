from unittest.mock import MagicMock
from uuid import uuid4

from app.db.models import Itinerary, TripState
from app.services.itinerary import ItineraryError, create_itinerary


def test_create_itinerary_rejects_incomplete_template():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    trip = TripState(id=uuid4(), destination="Paris")
    try:
        create_itinerary(db, trip)
        raise AssertionError("expected ItineraryError")
    except ItineraryError as exc:
        assert "incomplete" in str(exc)


def test_create_itinerary_rejects_second_generation():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = Itinerary()
    trip = TripState(id=uuid4(), destination="Paris", trip_type="Solo")
    try:
        create_itinerary(db, trip)
        raise AssertionError("expected ItineraryError")
    except ItineraryError as exc:
        assert "already exists" in str(exc)
