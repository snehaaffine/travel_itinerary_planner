from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_trip
from app.db.models import TripState
from app.db.session import get_db
from app.schemas import ProfileFeedbackRequest, StoryBeatRequest
from app.services.story import StoryError
from app.services.story_flow import (
    check_story_rate_limit,
    iter_story_events,
    record_profile_feedback,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/story/beat")
def story_beat(
    payload: StoryBeatRequest,
    request: Request,
    db: Session = Depends(get_db),
    trip: TripState = Depends(get_current_trip),
) -> StreamingResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not check_story_rate_limit(trip.id, client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    if not payload.tone and not payload.choice_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a genre or choice_ids",
        )
    if payload.tone and payload.choice_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Send tone or choice_ids, not both",
        )

    def events():
        try:
            for event, data in iter_story_events(
                db,
                trip,
                tone=payload.tone,
                choice_ids=payload.choice_ids,
            ):
                yield _sse(event, data)
        except StoryError as exc:
            yield _sse("error", {"detail": str(exc)})
        except Exception:
            logger.exception("Story beat stream failed")
            yield _sse("error", {"detail": "The narrator stalled. Try again."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/story/profile-feedback")
def story_profile_feedback(
    payload: ProfileFeedbackRequest,
    db: Session = Depends(get_db),
    trip: TripState = Depends(get_current_trip),
) -> dict:
    try:
        record_profile_feedback(db, trip, payload.vote)
    except StoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"vote": payload.vote}
