from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.db.models import TripPath, TripState
from app.services.agents import run_tool_agent
from app.services.itinerary import (
    ORCHESTRATOR_PROMPT,
    ORCHESTRATOR_PROMPT_STORY,
    _build_orchestrator_tools,
    _day_location_labels,
    _map_markers,
    _markers_for_day,
    _search_tool,
    _trip_brief,
    check_rate_limit,
    generate_itinerary_content,
)


class ScriptedLLM:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    def invoke(self, messages):
        assert self.responses, "ScriptedLLM has no remaining responses"
        return self.responses.pop(0)


def test_specialist_agent_calls_its_own_tool():
    called = {"n": 0}

    def weather_tool() -> str:
        called["n"] += 1
        return "22C and sunny"

    tool = StructuredTool.from_function(
        name="weather_tool",
        description="Get weather",
        func=weather_tool,
    )
    llm = ScriptedLLM(
        [
            AIMessage(
                content="",
                tool_calls=[{"id": "call-1", "name": "weather_tool", "args": {}}],
            ),
            AIMessage(content="Mostly sunny; good for outdoor time."),
        ]
    )

    run = run_tool_agent(system="You are weather.", user="Paris in August", tools=[tool], llm=llm)

    assert called["n"] == 1
    assert llm.bound_tool_names == ["weather_tool"]
    assert "sunny" in run.text


def test_orchestrator_exposes_specialist_agents_not_raw_tools():
    trip = TripState(
        id=uuid4(),
        destination="Paris",
        trip_type="Solo",
        interests=["Street Food"],
        pets=False,
    )
    tools = _build_orchestrator_tools(trip, {"lat": 48.8, "lon": 2.3, "place_id": "abc"})
    names = [tool.name for tool in tools]
    assert names == ["weather_agent", "poi_agent", "search_agent"]


def test_orchestrator_compiles_specialist_briefings_into_json(monkeypatch):
    monkeypatch.setattr(
        "app.services.itinerary._resolve_geo",
        lambda trip: {"lat": 48.8, "lon": 2.3, "place_id": "abc"},
    )
    monkeypatch.setattr(
        "app.services.itinerary.run_specialist",
        lambda **kwargs: f"[{kwargs['name']}] briefing",
    )

    itinerary_json = '{"days":[{"day":1,"summary":"Louvre morning","activities":[]}]}'
    llm = ScriptedLLM(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "w", "name": "weather_agent", "args": {}},
                    {"id": "p", "name": "poi_agent", "args": {}},
                ],
            ),
            AIMessage(content=itinerary_json),
        ]
    )
    trip = TripState(
        id=uuid4(),
        destination="Paris",
        trip_type="Solo",
        interests=["Museums & Art"],
        pets=False,
        dates={"start": "2026-08-17", "end": "2026-08-19"},
    )

    parsed = generate_itinerary_content(trip, llm_factory=lambda: llm)

    assert parsed["days"][0]["day"] == 1
    assert llm.bound_tool_names == ["weather_agent", "poi_agent", "search_agent"]
    assert not llm.responses


def test_run_tool_agent_runs_unknown_tool_without_raising():
    llm = ScriptedLLM(
        [
            AIMessage(
                content="",
                tool_calls=[{"id": "x", "name": "missing_tool", "args": {}}],
            ),
            AIMessage(content="Nothing found."),
        ]
    )
    def weather_stub() -> str:
        return "ok"

    tool = StructuredTool.from_function(
        name="weather_tool",
        description="Get weather",
        func=weather_stub,
    )
    run = run_tool_agent(system="s", user="u", tools=[tool], llm=llm)
    assert run.text == "Nothing found."


def test_run_tool_agent_finalizes_after_max_tool_rounds():
    called = {"n": 0}

    def weather_tool() -> str:
        called["n"] += 1
        return "22C"

    tool = StructuredTool.from_function(
        name="weather_tool",
        description="Get weather",
        func=weather_tool,
    )
    llm = ScriptedLLM(
        [
            AIMessage(
                content="",
                tool_calls=[{"id": "call-1", "name": "weather_tool", "args": {}}],
            ),
            AIMessage(content='{"days":[{"day":1,"activities":[]}]}'),
        ]
    )
    run = run_tool_agent(
        system="s",
        user="u",
        tools=[tool],
        max_rounds=1,
        llm=llm,
    )
    assert called["n"] == 1
    assert "days" in run.text


def test_story_brief_omits_budget_and_diet():
    trip = TripState(
        id=uuid4(),
        destination="Paris",
        path=TripPath.STORY,
        trip_type="Solo",
        interests=["Street Food"],
        food_preference="Street food",
        flavor_preference="Epic",
        dates={"start": "2026-08-17", "end": "2026-08-19"},
    )
    brief = _trip_brief(trip)
    assert "Path: story" in brief
    assert "Budget: not collected" in brief
    assert "Diet: not collected" in brief
    assert "Budget: Epic" not in brief
    assert "Diet: Street food" not in brief
    assert "Food style: Street food" in brief
    assert "Flavor: Epic" in brief
    assert "Versailles" in brief
    assert "flight" in brief.lower()


def test_template_brief_still_includes_budget_and_diet():
    trip = TripState(
        id=uuid4(),
        destination="Paris",
        path=TripPath.TEMPLATE,
        trip_type="Solo",
        interests=["Museums"],
        food_preference="Vegetarian",
        flavor_preference="Moderate",
    )
    brief = _trip_brief(trip)
    assert "Path: story" not in brief
    assert "Budget: Moderate" in brief
    assert "Diet: Vegetarian" in brief
    assert "Versailles" in brief


def test_search_tool_stubs_without_tavily_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.itinerary.get_settings",
        lambda: type("S", (), {"tavily_api_key": None})(),
    )
    tool = _search_tool()
    assert tool.func("paris parks") == "Search tool unavailable in this phase."


def test_search_tool_calls_tavily_when_keyed(monkeypatch):
    monkeypatch.setattr(
        "app.services.itinerary.get_settings",
        lambda: type("S", (), {"tavily_api_key": "tvly-test"})(),
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "results": [
                    {"title": "Park", "url": "https://example.com", "content": "green"}
                ]
            }

    monkeypatch.setattr(
        "app.services.itinerary.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )
    tool = _search_tool()
    payload = tool.func("quiet parks in Paris")
    assert "Park" in payload
    assert "example.com" in payload


def test_orchestrator_prompts_include_nearby_road_trips():
    for prompt in (ORCHESTRATOR_PROMPT, ORCHESTRATOR_PROMPT_STORY):
        assert "Versailles" in prompt
        assert "90 minutes" in prompt
        assert "flight" in prompt


def test_day_location_labels_include_activities_and_meals():
    labels = _day_location_labels(
        {
            "city": "Versailles",
            "activities": [
                {"title": "Palace visit", "location": "Palace of Versailles"},
                {"title": "Gardens", "place_name": "Gardens of Versailles"},
            ],
            "meals": [{"type": "Lunch", "venue": "Ore"}],
        }
    )
    assert labels == [
        "Palace of Versailles",
        "Gardens of Versailles",
        "Ore",
    ]


def test_map_markers_prefer_places_named_in_itinerary():
    places = [
        {"name": "Louvre", "formatted": "Louvre, Paris", "lat": 48.86, "lon": 2.337},
        {"name": "Hidden Cafe", "formatted": "Somewhere", "lat": 48.85, "lon": 2.3},
    ]
    content = {
        "days": [
            {
                "activities": [
                    {"title": "See art", "location": "Louvre"},
                ]
            }
        ]
    }
    markers = _map_markers(places, content)
    assert markers == [(2.337, 48.86, "activity")]


def test_markers_keep_one_pin_per_listed_stop():
    places = [
        {"name": "Louvre", "formatted": "Louvre", "lat": 48.86, "lon": 2.337},
        {"name": "Tuileries", "formatted": "Tuileries", "lat": 48.86, "lon": 2.337},
    ]
    day = {
        "day": 2,
        "city": "Paris",
        "activities": [
            {"title": "Louvre", "location": "Louvre"},
            {"title": "Garden", "location": "Tuileries"},
            {"title": "Walk", "location": "Louvre"},
        ],
        "meals": [{"type": "Dinner", "venue": "Somewhere Else"}],
    }
    markers = _markers_for_day(day, {"lat": 48.85, "lon": 2.3}, places)
    assert len(markers) == 4
    assert markers[0] == (2.337, 48.86)
    assert markers[1] != markers[0]
    assert markers[2] != markers[0]
    assert markers[-1][2] == "meal"


def test_rate_limit_skipped_outside_production(monkeypatch):
    monkeypatch.setattr(
        "app.services.itinerary.get_settings",
        lambda: type("S", (), {"rate_limits_enabled": False})(),
    )
    assert check_rate_limit(uuid4(), "127.0.0.1") is True
