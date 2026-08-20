import re

from app.constants import (
    BUDGETS_WITHOUT_FINE_DINING,
    COMMON_INTERESTS,
    DESTINATION_EXTRA_TAGS,
    FINE_DINING_TAG,
    INTEREST_FILTERS,
    MIN_INTEREST_TAGS,
    PAD_INTERESTS,
    STATIC_INTERESTS,
)

_SPLIT_RE = re.compile(r"[\s,&/+\-|]+")
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)
_FINE_DINING_KEYS = frozenset(
    {
        "fine dining",
        "fine dine",
        "luxury dining",
        "haute cuisine",
    }
)


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


def is_fine_dining(tag: str) -> bool:
    label = format_interest_label(tag)
    return bool(label) and label.lower() in _FINE_DINING_KEYS


def allows_fine_dining(budget: str | None) -> bool:
    if not budget:
        return True
    return budget not in BUDGETS_WITHOUT_FINE_DINING


def filter_interests_for_budget(tags: list[str], budget: str | None) -> list[str]:
    cleaned = unique_interest_tags(tags)
    if allows_fine_dining(budget):
        return cleaned
    return [tag for tag in cleaned if not is_fine_dining(tag)]


def interest_sentence(destination: str, interests: list[str] | None) -> str:
    place = (destination.split(",")[0] if destination else "").strip() or "this trip"
    tags = unique_interest_tags(list(interests or []))
    if not tags:
        return f"This {place} plan is a flexible mix of the city's everyday highlights."
    lowered = [tag.lower() for tag in tags]
    if len(lowered) == 1:
        return f"This {place} plan is shaped around {lowered[0]}."
    if len(lowered) == 2:
        return f"This {place} plan weaves together {lowered[0]} and {lowered[1]}."
    listed = ", ".join(lowered[:-1]) + f", and {lowered[-1]}"
    return f"This {place} plan weaves together {listed}."


def interests_for_destination(destination: str, budget: str | None = None) -> list[str]:
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

    tags = filter_interests_for_budget([*selected, *extras], budget)
    if len(tags) >= MIN_INTEREST_TAGS:
        return tags

    fillers = [*COMMON_INTERESTS, *PAD_INTERESTS]
    for tag in fillers:
        if tag == FINE_DINING_TAG and not allows_fine_dining(budget):
            continue
        rules = INTEREST_FILTERS.get(tag, {"include": (), "exclude": ()})
        exclude = rules.get("exclude") or ()
        if any(term in haystack for term in exclude):
            continue
        tags = unique_interest_tags([*tags, tag])
        if len(tags) >= MIN_INTEREST_TAGS:
            break
    return filter_interests_for_budget(tags, budget)
