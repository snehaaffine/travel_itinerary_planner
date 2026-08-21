from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_trip
from app.db.models import TripPath, TripState
from app.db.session import get_db
from app.main import app
from app.services.story import HolidayProfile
from app.services.story_flow import apply_canonical_values, iter_story_events

client = TestClient(app)
HEADERS = {"X-App-Token": "dev-app-token"}


class FakeDB:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:
        return None

    def query(self, _model):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        sessions = [item for item in self.added if getattr(item, "tone", None)]
        return sessions[-1] if sessions else None


def _trip() -> TripState:
    trip = TripState(
        id=uuid4(),
        destination="Paris, France",
        dates={"start": "2026-08-17", "end": "2026-08-19"},
    )
    trip.story_sessions = []
    return trip


def _override(trip: TripState, db: FakeDB) -> None:
    app.dependency_overrides[get_current_trip] = lambda: trip
    app.dependency_overrides[get_db] = lambda: db


def _clear() -> None:
    app.dependency_overrides.clear()


def test_apply_canonical_values_maps_story_bank_codes():
    trip = _trip()
    apply_canonical_values(trip, "trip_type", ["family_pet"])
    assert trip.trip_type == "Family"
    assert trip.pets is True
    apply_canonical_values(trip, "interests", ["sights", "food_drink"])
    assert trip.interests == ["Historic Sites", "Street Food"]
    apply_canonical_values(trip, "food_style", ["local_traditional"])
    assert trip.food_preference == "local_traditional"
    apply_canonical_values(trip, "wildcard_flavor", ["hidden_gems"])
    assert trip.flavor_preference == "hidden_gems"


def test_post_story_beat_starts_session_from_bank():
    trip = _trip()
    db = FakeDB()
    _override(trip, db)
    try:
        response = client.post("/story/beat", json={"tone": "Fantasy"}, headers=HEADERS)
        assert response.status_code == 200
        body = response.text
        assert "event: narrative" in body
        assert "event: beat" in body
        assert "event: done" in body
        assert "Paris, France" in body
        assert trip.path == TripPath.STORY
        session = db.added[-1]
        beats = session.beats["beats"]
        assert beats[0]["beat_number"] == 1
        assert beats[0]["field"] == "trip_type"
        assert beats[0]["options"][0]["id"] == "1"
        assert beats[0]["chosen_value"] is None
    finally:
        _clear()


def test_post_story_beat_rejects_unstocked_genre():
    trip = _trip()
    db = FakeDB()
    _override(trip, db)
    try:
        response = client.post("/story/beat", json={"tone": "Comedy"}, headers=HEADERS)
        assert response.status_code == 200
        assert "does not have a story" in response.text
    finally:
        _clear()


def test_post_story_beat_multi_select_then_profile(monkeypatch):
    trip = _trip()
    db = FakeDB()
    _override(trip, db)

    def fake_profile_events(*args, **kwargs):
        assert kwargs.get("destination") == "Paris, France"
        profile = HolidayProfile(
            pace="Unhurried",
            company="Alone",
            setting="Paris",
            comfort="Simple",
            food="Markets",
            adventure="Walks",
            assumptions=["They linger."],
            holiday="A slow week in Paris.",
        )
        yield SimpleNamespace(kind="holiday", text="A slow week")
        yield SimpleNamespace(kind="profile", profile=profile)

    monkeypatch.setattr(
        "app.services.story_flow.generate_holiday_profile_events", fake_profile_events
    )
    monkeypatch.setattr(
        "app.services.story_flow.maybe_summarize_story_context", lambda *args, **kwargs: None
    )
    try:
        start = client.post("/story/beat", json={"tone": "Fantasy"}, headers=HEADERS)
        assert start.status_code == 200
        for _beat in range(5):
            response = client.post(
                "/story/beat",
                json={"choice_ids": ["1"]},
                headers=HEADERS,
            )
            assert response.status_code == 200
            last = response
        assert "event: profile" in last.text
        assert '"ended": true' in last.text.replace(" ", "") or '"ended":true' in last.text.replace(
            " ", ""
        )
        assert trip.path == TripPath.STORY
        assert trip.trip_type == "Solo"
        assert trip.flavor_preference == "planned"
        assert trip.food_preference == "local_traditional"
        session = db.added[-1]
        assert session.beats["holiday_profile"]["holiday"] == "A slow week in Paris."
        assert session.beats["beats"][-1]["chosen_value"] == ["planned"]
    finally:
        _clear()


def test_iter_story_events_persists_multi_select_values():
    trip = _trip()
    db = FakeDB()
    events = list(iter_story_events(db, trip, tone="Mystery"))
    assert any(name == "beat" for name, _payload in events)
    follow = list(iter_story_events(db, trip, choice_ids=["1", "3"]))
    assert trip.trip_type == "Friends"
    assert any(name == "beat" for name, _payload in follow)
    session = db.added[-1]
    assert session.beats["beats"][0]["chosen_value"] == ["solo", "friends"]


def test_profile_feedback_records_vote(monkeypatch):
    trip = _trip()
    db = FakeDB()
    _override(trip, db)

    def fake_profile_events(*args, **kwargs):
        profile = HolidayProfile(
            pace="Unhurried",
            company="Alone",
            setting="Paris",
            comfort="Simple",
            food="Markets",
            adventure="Walks",
            assumptions=["They linger."],
            holiday="A slow week in Paris.",
        )
        yield SimpleNamespace(kind="holiday", text="A slow week")
        yield SimpleNamespace(kind="profile", profile=profile)

    monkeypatch.setattr(
        "app.services.story_flow.generate_holiday_profile_events", fake_profile_events
    )
    monkeypatch.setattr(
        "app.services.story_flow.maybe_summarize_story_context", lambda *args, **kwargs: None
    )
    try:
        client.post("/story/beat", json={"tone": "Western"}, headers=HEADERS)
        for _beat in range(5):
            client.post("/story/beat", json={"choice_ids": ["1"]}, headers=HEADERS)
        response = client.post(
            "/story/profile-feedback",
            json={"vote": "up"},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["vote"] == "up"
        session = db.added[-1]
        assert session.beats["profile_feedback"] == "up"
    finally:
        _clear()


def test_create_trip_leaves_path_unset(monkeypatch):
    stored: dict = {}

    class TripDB(FakeDB):
        def add(self, obj) -> None:
            stored["trip"] = obj
            if getattr(obj, "pets", None) is None:
                obj.pets = False
            super().add(obj)

    monkeypatch.setattr(
        "app.api.trips._resolve_geo",
        lambda payload: {
            "formatted": payload.destination,
            "lat": 48.8,
            "lon": 2.3,
            "place_id": "abc",
        },
    )
    monkeypatch.setattr("app.api.trips.cache_trip_geo", lambda *args, **kwargs: None)
    app.dependency_overrides[get_db] = lambda: TripDB()
    try:
        response = client.post(
            "/trip",
            json={"destination": "Paris, France"},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["path"] is None
        assert stored["trip"].path is None
    finally:
        _clear()
