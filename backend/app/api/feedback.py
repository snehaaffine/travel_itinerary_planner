from fastapi import APIRouter, Depends
from sqlalchemy.orm import object_session

from app.api.deps import get_current_trip
from app.db.models import Feedback, TripState
from app.schemas import FeedbackCreate

router = APIRouter()


@router.post("/feedback")
def submit_feedback(payload: FeedbackCreate, trip: TripState = Depends(get_current_trip)) -> dict:
    db = object_session(trip)
    assert db is not None
    entry = Feedback(trip_state_id=trip.id, rating=payload.rating, comment=payload.comment)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": str(entry.id), "rating": entry.rating, "comment": entry.comment}
