import re

from app.constants import (
    COMMON_INTERESTS,
    DESTINATION_EXTRA_TAGS,
    INTEREST_FILTERS,
    MIN_INTEREST_TAGS,
    PAD_INTERESTS,
    STATIC_INTERESTS,
)

_SPLIT_RE = re.compile(r"[\s,&/+\-|]+")
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)


def format_interest_label(raw: str) -> str | None:
    cleaned = _AND_RE.sub(" ", raw.strip())
    words = [part for part in _SPLIT_RE.split(cleaned) if part]
    if not words:
        return None
    titled = [word[:1].upper() + word[1:].lower() for word in words[:2]]
    return " ".join(titled)


def unique_interest_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        label = format_interest_label(tag)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(label)
    return unique


def interests_for_destination(destination: str) -> list[str]:
    haystack = destination.strip().lower()
    selected: list[str] = []
    for tag in STATIC_INTERESTS:
        rules = INTEREST_FILTERS.get(tag, {"include": (), "exclude": ()})
        exclude = rules.get("exclude") or ()
        include = rules.get("include") or ()
        if any(term in haystack for term in exclude):
            continue
        if include and not any(term in haystack for term in include):
            continue
        selected.append(tag)

    extras: list[str] = []
    for needle, tags in DESTINATION_EXTRA_TAGS.items():
        if needle in haystack:
            extras.extend(tags)

    tags = unique_interest_tags([*selected, *extras])
    if len(tags) >= MIN_INTEREST_TAGS:
        return tags

    fillers = [*COMMON_INTERESTS, *PAD_INTERESTS]
    for tag in fillers:
        rules = INTEREST_FILTERS.get(tag, {"include": (), "exclude": ()})
        exclude = rules.get("exclude") or ()
        if any(term in haystack for term in exclude):
            continue
        tags = unique_interest_tags([*tags, tag])
        if len(tags) >= MIN_INTEREST_TAGS:
            break
    return tags
