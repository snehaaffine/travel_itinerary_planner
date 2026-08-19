from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.config import get_settings

APP_TOKEN_HEADER = "X-App-Token"
EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class AppTokenMiddleware(BaseHTTPMiddleware):
  async def dispatch(
    self, request: Request, call_next: RequestResponseEndpoint
  ) -> Response:
    if request.url.path in EXEMPT_PATHS:
      return await call_next(request)

    settings = get_settings()
    token = request.headers.get(APP_TOKEN_HEADER)

    if not token or token != settings.app_api_token:
      return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid or missing app token"},
      )

    return await call_next(request)


def verify_app_token(request: Request) -> None:
  """Dependency for routes that need explicit app-token verification."""
  settings = get_settings()
  token = request.headers.get(APP_TOKEN_HEADER)

  if not token or token != settings.app_api_token:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or missing app token",
    )
