from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_trip
from app.auth.session import create_session_cookie
from app.db.models import TripState
from app.db.session import get_db
from app.schemas import TripCreate, TripDatesUpdate, TripResponse, parse_diets
from app.services.geo_store import cache_geocode, cache_trip_geo, get_cached_geocode
from app.services.geoapify.common import GeoapifyError
from app.services.geoapify.poi import geocode_destination

router = APIRouter()


def _trip_response(trip: TripState) -> TripResponse:
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


def _resolve_geo(payload: TripCreate) -> dict:
    cache_key = payload.place_id or payload.destination
    cached = get_cached_geocode(cache_key)
    if cached:
        return cached
    if payload.lat is not None and payload.lon is not None and payload.place_id:
        geo = {
            "name": payload.destination,
            "formatted": payload.destination,
            "place_id": payload.place_id,
            "lat": payload.lat,
            "lon": payload.lon,
        }
        cache_geocode(cache_key, geo)
        return geo
    geo = geocode_destination(payload.destination, place_id=payload.place_id)
    cache_geocode(cache_key, geo)
    return geo


@router.post("/trip", response_model=TripResponse)
def create_trip(
    payload: TripCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> TripResponse:
    try:
        geo = _resolve_geo(payload)
    except GeoapifyError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    destination = geo.get("formatted") or payload.destination
    trip = TripState(
        destination=destination,
        dates=payload.dates,
        path=None,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    cache_trip_geo(trip.id, geo)
    create_session_cookie(response, trip.id)
    return _trip_response(trip)


@router.put("/trip/dates", response_model=TripResponse)
def update_trip_dates(
    payload: TripDatesUpdate,
    db: Session = Depends(get_db),
    trip: TripState = Depends(get_current_trip),
) -> TripResponse:
    trip.dates = None if payload.skip_dates else payload.dates
    db.commit()
    db.refresh(trip)
    return _trip_response(trip)
