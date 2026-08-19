from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.session import get_trip_state_id_from_cookie
from app.db.models import TripState
from app.db.session import get_db


def get_current_trip(
    trip_id: UUID = Depends(get_trip_state_id_from_cookie),
    db: Session = Depends(get_db),
) -> TripState:
    trip = db.get(TripState, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip
