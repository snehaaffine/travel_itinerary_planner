from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.destinations import router as destinations_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.itinerary import router as itinerary_router
from app.api.template import router as template_router
from app.api.trips import router as trips_router
from app.auth.app_token import AppTokenMiddleware
from app.config import get_settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
  init_db()
  yield


def create_app() -> FastAPI:
  settings = get_settings()

  app = FastAPI(
    title="Travel Itinerary Planner API",
    version="0.1.0",
    lifespan=lifespan,
  )

  app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )
  app.add_middleware(AppTokenMiddleware)

  app.include_router(health_router)
  app.include_router(destinations_router)
  app.include_router(trips_router)
  app.include_router(template_router)
  app.include_router(itinerary_router)
  app.include_router(feedback_router)

  return app


app = create_app()
