from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import object_session

from app.api.deps import get_current_trip
from app.constants import DIET_OPTIONS
from app.db.models import TripPath, TripState
from app.schemas import TemplateSubmit, TripResponse, parse_diets, serialize_diets
from app.services.interests import interests_for_destination

router = APIRouter()


def trip_response(trip: TripState) -> TripResponse:
    return TripResponse(
        id=trip.id,
        destination=trip.destination,
        dates=trip.dates,
        path=trip.path.value if trip.path else None,
        trip_type=trip.trip_type,
        pets=trip.pets,
        interests=trip.interests,
        budget=trip.flavor_preference,
        diets=parse_diets(trip.food_preference),
    )


@router.get("/template/interests")
def list_interests(destination: str = Query(min_length=1, max_length=200)) -> dict[str, list[str]]:
    return {"tags": interests_for_destination(destination)}


@router.post("/template", response_model=TripResponse)
def submit_template(
    payload: TemplateSubmit,
    trip: TripState = Depends(get_current_trip),
) -> TripResponse:
    allowed = {option.lower() for option in DIET_OPTIONS}
    diets = [diet for diet in payload.diets if diet.strip().lower() in allowed]
    trip.path = TripPath.TEMPLATE
    trip.trip_type = payload.trip_type
    trip.pets = payload.pets
    trip.interests = payload.interests
    trip.flavor_preference = payload.budget
    trip.food_preference = serialize_diets(diets)
    db = object_session(trip)
    assert db is not None
    db.commit()
    db.refresh(trip)
    return trip_response(trip)
