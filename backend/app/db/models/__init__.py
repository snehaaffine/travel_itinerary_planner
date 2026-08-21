import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TripPath(str, enum.Enum):
    STORY = "story"
    TEMPLATE = "template"


class TripState(Base):
    __tablename__ = "trip_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    dates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    path: Mapped[TripPath | None] = mapped_column(
        Enum(TripPath, name="trip_path"), nullable=True
    )
    trip_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pets: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    interests: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    pace: Mapped[str | None] = mapped_column(String(50), nullable=True)
    food_preference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    flavor_preference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    story_sessions: Mapped[list["StorySession"]] = relationship(
        back_populates="trip_state", cascade="all, delete-orphan"
    )
    itineraries: Mapped[list["Itinerary"]] = relationship(
        back_populates="trip_state", cascade="all, delete-orphan"
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(
        back_populates="trip_state", cascade="all, delete-orphan"
    )


class StorySession(Base):
    __tablename__ = "story_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trip_state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_state.id"), nullable=False, index=True
    )
    tone: Mapped[str] = mapped_column(String(100), nullable=False)
    beats: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trip_state: Mapped["TripState"] = relationship(back_populates="story_sessions")


class Itinerary(Base):
    __tablename__ = "itineraries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trip_state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_state.id"), nullable=False, index=True
    )
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    map_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trip_state: Mapped["TripState"] = relationship(back_populates="itineraries")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trip_state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_state.id"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trip_state: Mapped["TripState"] = relationship(back_populates="feedback_entries")
