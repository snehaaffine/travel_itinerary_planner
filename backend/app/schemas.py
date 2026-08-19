from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DestinationSuggestion(BaseModel):
    name: str
    formatted: str
    country: str | None = None
    place_id: str
    lat: float
    lon: float


class TripCreate(BaseModel):
    destination: str
    place_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    dates: dict[str, str] | None = None


class TripDatesUpdate(BaseModel):
    dates: dict[str, str] | None = None
    skip_dates: bool = False


class TemplateSubmit(BaseModel):
    trip_type: Literal["Solo", "Couple", "Friends", "Family"]
    pets: bool = False
    interests: list[str] = Field(default_factory=list)
    budget: Literal["Budget-friendly", "Moderate", "Comfortable", "Luxury"]
    diets: list[str] = Field(default_factory=list)


def parse_diets(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def serialize_diets(diets: list[str]) -> str | None:
    cleaned = [item.strip() for item in diets if item.strip()]
    return ", ".join(cleaned) or None


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class TripResponse(BaseModel):
    id: UUID
    destination: str
    dates: dict[str, Any] | None
    path: str | None
    trip_type: str | None
    pets: bool
    interests: list[Any] | None
    budget: str | None = None
    diets: list[str] = Field(default_factory=list)
