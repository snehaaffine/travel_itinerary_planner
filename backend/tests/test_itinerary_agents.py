import json
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.db.models import TripState
from app.services.agents import run_tool_agent
from app.services.itinerary import _build_orchestrator_tools, generate_itinerary_content


class ScriptedLLM:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.bound_tool_names: list[str] = []
        self.prompts: list[str] = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    def invoke(self, messages):
        assert self.responses, "ScriptedLLM has no remaining responses"
        user = next(
            (
                message.content
                for message in reversed(messages)
                if getattr(message, "content", None)
            ),
            "",
        )
        if isinstance(user, str):
            self.prompts.append(user)
        return self.responses.pop(0)


def _trip(**kwargs) -> TripState:
    defaults = dict(
        id=uuid4(),
        destination="Paris",
        trip_type="Solo",
        interests=["Museums"],
        pets=False,
        dates={"start": "2026-08-17", "end": "2026-08-19"},
    )
    defaults.update(kwargs)
    return TripState(**defaults)


def _day(day: int, place: str) -> dict:
    return {
        "day": day,
        "summary": place,
        "activities": [{"title": place, "description": place, "location": place}],
        "meals": [{"type": "Lunch", "venue": f"{place} Cafe"}],
    }


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
    tools = _build_orchestrator_tools(
        _trip(dates=None),
        {"lat": 48.8, "lon": 2.3, "place_id": "abc"},
    )
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

    itinerary_json = {
        "days": [_day(1, "Louvre"), _day(2, "Orsay"), _day(3, "Rodin")],
        "notes": "",
    }
    llm = ScriptedLLM(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "w", "name": "weather_agent", "args": {}},
                    {"id": "p", "name": "poi_agent", "args": {}},
                ],
            ),
            AIMessage(content=json.dumps(itinerary_json)),
        ]
    )
    parsed = generate_itinerary_content(_trip(), llm_factory=lambda: llm)

    assert [day["day"] for day in parsed["days"]] == [1, 2, 3]
    assert parsed["days"][0]["date"] == "2026-08-17"
    assert llm.bound_tool_names == ["weather_agent", "poi_agent", "search_agent"]
    assert not llm.responses


def test_seven_day_trip_chunks_and_drops_repeated_places(monkeypatch):
    monkeypatch.setattr(
        "app.services.itinerary._resolve_geo",
        lambda trip: {"lat": 48.8, "lon": 2.3, "place_id": "abc"},
    )
    monkeypatch.setattr(
        "app.services.itinerary.run_specialist",
        lambda **kwargs: f"[{kwargs['name']}] briefing",
    )

    llm = ScriptedLLM(
        [
            AIMessage(
                content=json.dumps(
                    {"days": [_day(1, "Louvre"), _day(2, "Orsay"), _day(3, "Rodin")]}
                )
            ),
            AIMessage(
                content=json.dumps(
                    {"days": [_day(4, "Louvre"), _day(5, "Marais"), _day(6, "Canal")]}
                )
            ),
            AIMessage(content=json.dumps({"days": [_day(7, "Sacre Coeur")]})),
        ]
    )
    trip = _trip(dates={"start": "2026-08-17", "end": "2026-08-23"})
    parsed = generate_itinerary_content(trip, llm_factory=lambda: llm)

    assert [day["day"] for day in parsed["days"]] == [1, 2, 3, 4, 5, 6, 7]
    assert parsed["days"][3]["date"] == "2026-08-20"
    assert parsed["days"][6]["date"] == "2026-08-23"
    places = [
        activity["location"]
        for day in parsed["days"]
        for activity in day["activities"]
    ]
    assert places == ["Louvre", "Orsay", "Rodin", "Marais", "Canal", "Sacre Coeur"]
    assert parsed["days"][3]["activities"] == []
    avoid_prompt = llm.prompts[1]
    assert "Already used places" in avoid_prompt
    assert "Louvre" in avoid_prompt
    assert "Day 4" in avoid_prompt
    assert "Day 7" not in llm.prompts[1]


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
