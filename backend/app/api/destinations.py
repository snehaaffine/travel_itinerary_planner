from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import DestinationSuggestion
from app.services.geoapify.common import GeoapifyError
from app.services.geoapify.poi import autocomplete_cities

router = APIRouter()


@router.get("/destinations/suggest", response_model=list[DestinationSuggestion])
def suggest_destinations(
    q: str = Query(min_length=2, max_length=120),
) -> list[DestinationSuggestion]:
    try:
        places = autocomplete_cities(q)
    except GeoapifyError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [DestinationSuggestion(**place) for place in places]
