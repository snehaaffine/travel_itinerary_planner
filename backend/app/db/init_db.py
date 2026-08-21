from sqlalchemy import text

from app.db.base import Base
from app.db.models import Feedback, Itinerary, StorySession, TripState  # noqa: F401
from app.db.session import engine


def init_db() -> None:
  """Create all tables from SQLAlchemy models if they do not exist."""
  Base.metadata.create_all(bind=engine)
  with engine.begin() as connection:
    connection.execute(text("ALTER TABLE itineraries ADD COLUMN IF NOT EXISTS map_image_url TEXT"))
