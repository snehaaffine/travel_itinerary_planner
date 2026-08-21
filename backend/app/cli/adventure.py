from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap

from app.services.story import (
    STORY_GENRES,
    STORY_TURNS,
    HolidayProfile,
    StoryChoice,
    StoryError,
    StoryEvent,
    StoryTurn,
    generate_holiday_profile,
    parse_choice_input,
    resolve_genre,
)
from app.services.story_bank import beat_for, is_stocked, stocked_genres


def _width() -> int:
    return max(60, min(shutil.get_terminal_size((88, 24)).columns, 100))


def _print_wrapped(text: str) -> None:
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            print()
            continue
        print(textwrap.fill(paragraph, width=_width()))


def _print_themes() -> None:
    print("Choose one theme:")
    stocked = set(stocked_genres())
    for index, genre in enumerate(STORY_GENRES, start=1):
        suffix = "" if genre in stocked else " (not yet written)"
        print(f"  {index}. {genre}{suffix}")


def _turn_from_beat(beat: dict) -> StoryTurn:
    choices = [
        StoryChoice(
            id=str(option["id"]),
            text=str(option["label"]),
            value=str(option["value"]),
        )
        for option in beat.get("options") or []
    ]
    return StoryTurn(
        scene=str(beat.get("narrative_text") or ""),
        field=str(beat.get("field") or ""),
        choices=choices,
    )


def _print_turn(turn: StoryTurn, turn_number: int) -> None:
    print()
    print("─" * _width())
    print(f"Beat {turn_number} of {STORY_TURNS}  ·  {turn.field}")
    print("─" * _width())
    _print_wrapped(turn.scene)
    print()
    print("Choose one or more options (example: 1  or  1,3):")
    for choice in turn.choices:
        print(f"  [{choice.id}] {choice.text}")


def _print_profile(profile: HolidayProfile) -> None:
    print()
    print("═" * _width())
    print("Holiday profile")
    print("═" * _width())
    print(json.dumps(profile.to_dict(), indent=2))


def _read_theme(passed: str | None) -> str:
    if passed:
        matched = resolve_genre(passed)
        if matched and is_stocked(matched):
            return matched
        print(f"Unknown or unstocked theme {passed!r}. Choose from the list.")
    print("A 5-beat story. First pick one theme. Then five choices, then a holiday profile.")
    while True:
        _print_themes()
        raw = input("Your theme (1–11): ").strip()
        if "," in raw or " " in raw:
            print("Pick one theme only.")
            continue
        matched = resolve_genre(raw)
        if matched and is_stocked(matched):
            return matched
        if matched:
            print("That genre does not have a story yet.")
            continue
        print("Enter a stocked theme: Fantasy, Mystery, Sci-Fi, or Western.")


def _call_agent(label: str, fn):
    try:
        return fn()
    except StoryError as exc:
        print(f"The narrator stalled ({exc}). Try again.")
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"Could not reach the story agent ({label}): {exc}")
        return None


def play(genre: str) -> None:
    history: list[StoryEvent] = []
    print()
    _print_wrapped(f"Theme: {genre}")
    print(f"{STORY_TURNS} beats, then a holiday profile.")
    print("Type q to quit. You can pick several choices at once.")

    for turn_number in range(1, STORY_TURNS + 1):
        beat = beat_for(genre, turn_number, "your destination")
        turn = _turn_from_beat(beat)
        _print_turn(turn, turn_number)

        quit_early = False
        while True:
            raw = input("\nYour choice: ").strip()
            if raw.lower() in {"q", "quit", "exit"}:
                quit_early = True
                break
            try:
                picks = parse_choice_input(raw, turn.choices)
                selected = [pick.text for pick in picks]
                history.append(
                    StoryEvent(
                        scene=turn.scene,
                        field=turn.field,
                        selected=selected,
                        values=[pick.value or pick.text for pick in picks],
                    )
                )
                break
            except StoryError as exc:
                print(exc)
        if quit_early:
            if not history:
                print("Story paused.")
                return
            print("Stopping early. Reading the choices you already made.")
            break

    if not history:
        print("No choices to read.")
        return
    profile = _call_agent(
        "holiday reading",
        lambda: generate_holiday_profile(genre, history),
    )
    if profile is None:
        return
    _print_profile(profile)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PRD story path: pick one theme, play 5 beats, get a holiday profile.",
    )
    parser.add_argument(
        "-t",
        "--theme",
        dest="theme",
        help="Skip the menu by passing a theme name or number, for example Fantasy or 1",
    )
    args = parser.parse_args(argv)
    try:
        genre = _read_theme(args.theme)
    except EOFError:
        return 1
    try:
        play(genre)
    except KeyboardInterrupt:
        print("\nStory paused.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
