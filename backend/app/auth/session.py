import uuid

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

SESSION_MAX_AGE_SECONDS = 86400  # 24 hours


def _get_serializer() -> URLSafeTimedSerializer:
  settings = get_settings()
  return URLSafeTimedSerializer(settings.session_secret, salt="trip-session")


def create_session_cookie(response: Response, trip_state_id: uuid.UUID) -> None:
  """Set a signed httpOnly session cookie bound to a trip_state."""
  settings = get_settings()
  serializer = _get_serializer()
  signed_value = serializer.dumps(str(trip_state_id))

  response.set_cookie(
    key=settings.session_cookie_name,
    value=signed_value,
    httponly=True,
    samesite="lax",
    secure=settings.session_cookie_secure,
    max_age=SESSION_MAX_AGE_SECONDS,
  )


def get_trip_state_id_from_cookie(request: Request) -> uuid.UUID:
  """Read and validate the session cookie, returning the trip_state UUID."""
  settings = get_settings()
  signed_value = request.cookies.get(settings.session_cookie_name)

  if not signed_value:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Session cookie missing",
    )

  serializer = _get_serializer()
  try:
    trip_state_id = serializer.loads(signed_value, max_age=SESSION_MAX_AGE_SECONDS)
  except (BadSignature, SignatureExpired):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or expired session",
    )

  return uuid.UUID(trip_state_id)
