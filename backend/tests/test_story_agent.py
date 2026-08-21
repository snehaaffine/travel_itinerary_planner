import json

from langchain_core.messages import AIMessage

from app.services.story import (
    STORY_GENRES,
    STORY_TURNS,
    StoryChoice,
    StoryError,
    StoryEvent,
    fallback_turn,
    generate_holiday_profile,
    generate_turn,
    normalize_turn,
    parse_choice_input,
    parse_story_turn,
    resolve_genre,
)


class ScriptedLLM:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.prompts: list[str] = []

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


def test_prd_has_eleven_genres_and_five_beats():
    assert len(STORY_GENRES) == 11
    assert "Fantasy" in STORY_GENRES
    assert "Comedy" in STORY_GENRES
    assert STORY_TURNS == 5


def test_resolve_genre_from_name_or_number():
    assert resolve_genre("fantasy") == "Fantasy"
    assert resolve_genre("6") == "Adventure/Pirate"
    assert resolve_genre("noir") == "Noir Detective"
    assert resolve_genre("haunted library") is None


def test_parse_story_turn_from_prd_shape():
    wrapped = """```json
    {"narrative_text": "A clock ticks in an empty classroom.",
     "field": "pace",
     "options": [
       {"label": "Sit still", "value": "Unhurried"},
       {"label": "Chase the sound", "value": "Packed"}
     ],}
    ```"""
    turn = parse_story_turn(wrapped, turn_number=3)
    assert "classroom" in turn.scene
    assert [choice.text for choice in turn.choices] == ["Sit still", "Chase the sound"]
    assert turn.choices[0].value == "Unhurried"


def test_normalize_turn_allows_legacy_scene_choices():
    playing = normalize_turn(
        {"scene": "Rain on the glass.", "choices": ["Stay put", "Go outside"]},
        turn_number=1,
    )
    assert [choice.id for choice in playing.choices] == ["1", "2"]


def test_parse_choice_input_allows_multiple_selections():
    choices = [
        StoryChoice(id="1", text="Open the book", value="Unhurried"),
        StoryChoice(id="2", text="Call the cat", value="Pets"),
        StoryChoice(id="3", text="Hide", value="Solo"),
    ]
    picked = parse_choice_input("1, 3", choices)
    assert [choice.value for choice in picked] == ["Unhurried", "Solo"]


def test_parse_choice_input_rejects_empty_and_unknown():
    choices = [StoryChoice(id="1", text="Stay"), StoryChoice(id="2", text="Go")]
    try:
        parse_choice_input("", choices)
        raise AssertionError("expected StoryError")
    except StoryError:
        pass
    try:
        parse_choice_input("9", choices)
        raise AssertionError("expected StoryError")
    except StoryError:
        pass


def test_generate_turn_uses_prd_genre_and_beat_field():
    payload = {
        "narrative_text": "The forest path splits under two moons.",
        "field": "trip_type",
        "options": [
            {"label": "Walk it alone", "value": "Solo"},
            {"label": "Wait for a companion", "value": "Couple"},
        ],
    }
    llm = ScriptedLLM([AIMessage(content=json.dumps(payload))])
    turn = generate_turn("Fantasy", llm_factory=lambda: llm, turn_number=1)
    assert turn.field == "trip_type"
    assert len(turn.choices) == 2
    assert "Genre: Fantasy" in llm.prompts[0]
    assert "trip_type" in llm.prompts[0]
    assert "Beat 1 of 5" in llm.prompts[0]


def test_generate_turn_falls_back_when_json_is_bad():
    llm = ScriptedLLM(
        [
            AIMessage(content="not json"),
            AIMessage(content="still not json"),
        ]
    )
    turn = generate_turn("Mystery", llm_factory=lambda: llm, turn_number=3)
    fallback = fallback_turn(3)
    assert turn.field == "pace"
    assert [choice.value for choice in turn.choices] == [
        choice.value for choice in fallback.choices
    ]


def test_generate_holiday_profile_matches_example_shape():
    payload = {
        "pace": "Unhurried",
        "company": "Alone or with one other person",
        "setting": "Quiet countryside and small towns",
        "comfort": "Simple, local, not polished",
        "food": "Markets and neighborhood kitchens",
        "adventure": "Gentle walks, not extreme sports",
        "assumptions": [
            "They linger rather than rush.",
            "They avoid crowds.",
        ],
        "holiday": (
            "A slow week in the countryside, walking between villages and eating simply."
        ),
    }
    llm = ScriptedLLM([AIMessage(content=json.dumps(payload))])
    history = [
        StoryEvent(
            scene="A path splits.",
            field="pace",
            selected=["Take the quiet lane"],
            values=["Unhurried"],
        ),
        StoryEvent(
            scene="A door opens.",
            field="trip_type",
            selected=["Sit by the fire"],
            values=["Solo"],
        ),
    ]
    profile = generate_holiday_profile("Fantasy", history, llm_factory=lambda: llm)
    assert profile.to_dict() == payload
    assert "example JSON shape" in llm.prompts[0]
    assert "Unhurried" in llm.prompts[0]
    assert "Dates: unknown" in llm.prompts[0]


def test_generate_holiday_profile_includes_destination_and_dates():
    payload = {
        "pace": "Unhurried",
        "company": "Solo",
        "setting": "Paris",
        "comfort": "Simple",
        "food": "Markets",
        "adventure": "Walks",
        "assumptions": ["They linger."],
        "holiday": "A slow week in Paris.",
    }
    llm = ScriptedLLM([AIMessage(content=json.dumps(payload))])
    generate_holiday_profile(
        "Fantasy",
        [
            StoryEvent(
                scene="A path splits.",
                field="pace",
                selected=["Take the quiet lane"],
                values=["Unhurried"],
            )
        ],
        llm_factory=lambda: llm,
        destination="Paris, France",
        dates={"start": "2026-08-17", "end": "2026-08-19"},
    )
    prompt = llm.prompts[0]
    assert "Paris, France" in prompt
    assert "2026-08-17" in prompt


def test_extract_partial_json_string_from_incomplete_object():
    from app.services.story import extract_partial_json_string

    partial = '{"narrative_text": "The forest path splits'
    assert extract_partial_json_string(partial, "narrative_text") == "The forest path splits"
    complete = '{"narrative_text": "Done.", "field": "pace"}'
    assert extract_partial_json_string(complete, "narrative_text") == "Done."


def test_generate_turn_events_streams_narrative_then_turn():
    from app.services.story import generate_turn_events

    chunks = [
        '{"narrative_text": "The forest',
        ' path splits under two moons.", "field": "trip_type",',
        ' "options": [{"label": "Walk it alone", "value": "Solo"},',
        ' {"label": "Wait for a companion", "value": "Couple"}]}',
    ]

    class StreamingLLM:
        def stream(self, messages):
            for chunk in chunks:
                yield AIMessage(content=chunk)

        def invoke(self, messages):
            raise AssertionError("invoke should not run when stream works")

    events = list(
        generate_turn_events("Fantasy", llm_factory=lambda: StreamingLLM(), turn_number=1)
    )
    narratives = [event.text for event in events if event.kind == "narrative"]
    assert narratives[0] == "The forest"
    assert narratives[-1] == "The forest path splits under two moons."
    turns = [event.turn for event in events if event.kind == "turn"]
    assert turns[-1] is not None
    assert turns[-1].field == "trip_type"


def test_story_bank_has_four_stocked_genres():
    from app.services.story_bank import load_story_bank, stocked_genres

    load_story_bank.cache_clear()
    assert stocked_genres() == ("Fantasy", "Mystery", "Sci-Fi", "Western")


def test_maybe_summarize_skips_short_context(monkeypatch):
    from app.services.story import HolidayProfile, StoryEvent, maybe_summarize_story_context

    called = {"n": 0}

    class Boom:
        def invoke(self, messages):
            called["n"] += 1
            raise AssertionError("should not summarize short context")

    summary = maybe_summarize_story_context(
        [
            StoryEvent(
                scene="A path splits.",
                field="pace",
                selected=["leisurely"],
                values=["leisurely"],
            )
        ],
        HolidayProfile(
            pace="Unhurried",
            company="Alone",
            setting="Paris",
            comfort="Simple",
            food="Markets",
            adventure="Walks",
            assumptions=["They linger."],
            holiday="A slow week in Paris.",
        ),
        llm_factory=lambda: Boom(),
    )
    assert summary is None
    assert called["n"] == 0


def test_maybe_summarize_fires_when_over_threshold(monkeypatch):
    from app.services import story as story_mod
    from app.services.story import HolidayProfile, StoryEvent, maybe_summarize_story_context

    monkeypatch.setattr(story_mod, "STORY_CONTEXT_SUMMARIZE_TOKENS", 1)
    payload = {
        "pace": "Unhurried",
        "company": "Alone",
        "setting": "Paris",
        "comfort": "Simple",
        "food": "Markets",
        "adventure": "Walks",
        "assumptions": ["They linger."],
        "holiday": "A slow week in Paris.",
    }
    llm = ScriptedLLM([AIMessage(content=json.dumps(payload))])
    summary = maybe_summarize_story_context(
        [
            StoryEvent(
                scene="A very long scene " * 20,
                field="pace",
                selected=["leisurely"],
                values=["leisurely"],
            )
        ],
        HolidayProfile(**payload),
        llm_factory=lambda: llm,
    )
    assert summary["holiday"] == "A slow week in Paris."
