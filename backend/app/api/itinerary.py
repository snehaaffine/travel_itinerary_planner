import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import object_session

from app.api.deps import get_current_trip
from app.db.models import Itinerary, TripState
from app.services.itinerary import (
    USER_GENERATION_ERROR,
    ItineraryError,
    check_rate_limit,
    create_itinerary,
    get_or_create_map_image,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/itinerary")
def generate_itinerary(request: Request, trip: TripState = Depends(get_current_trip)) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(trip.id, client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    db = object_session(trip)
    assert db is not None
    try:
        itinerary = create_itinerary(db, trip)
    except ItineraryError as exc:
        message = str(exc)
        if "already exists" in message:
            code = status.HTTP_409_CONFLICT
        elif "incomplete" in message:
            code = status.HTTP_400_BAD_REQUEST
        else:
            code = status.HTTP_502_BAD_GATEWAY
            cause = exc.__cause__
            logger.exception(
                "Itinerary generation failed: %s%s",
                message,
                f" (cause: {cause})" if cause else "",
            )
            message = USER_GENERATION_ERROR
        raise HTTPException(status_code=code, detail=message) from exc
    return {
        "id": str(itinerary.id),
        "content": itinerary.content,
        "map_image_url": itinerary.map_image_url,
    }


@router.get("/itinerary/map")
@router.get("/itinerary/map/{day_number}")
def get_itinerary_map(
    trip: TripState = Depends(get_current_trip),
    day_number: int = 1,
) -> Response:
    db = object_session(trip)
    assert db is not None
    itinerary = db.query(Itinerary).filter(Itinerary.trip_state_id == trip.id).first()
    if itinerary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No itinerary yet")
    png = get_or_create_map_image(itinerary, trip, day_number)
    if not png:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map unavailable")
    media = "image/png" if png.startswith(b"\x89PNG") else "image/jpeg"
    return Response(content=png, media_type=media)


@router.get("/itinerary")
def get_itinerary(trip: TripState = Depends(get_current_trip)) -> dict:
    db = object_session(trip)
    assert db is not None
    itinerary = db.query(Itinerary).filter(Itinerary.trip_state_id == trip.id).first()
    if itinerary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No itinerary yet")
    return {
        "id": str(itinerary.id),
        "content": itinerary.content,
        "map_image_url": itinerary.map_image_url,
    }
