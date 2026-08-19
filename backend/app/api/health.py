from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cache.redis import ping_redis
from app.db.session import SessionLocal

router = APIRouter()


def _check_db() -> str:
  try:
    db: Session = SessionLocal()
    db.execute(text("SELECT 1"))
    db.close()
    return "ok"
  except Exception:
    return "error"


@router.get("/health")
def health_check() -> dict[str, str]:
  db_status = _check_db()
  redis_status = "ok" if ping_redis() else "error"
  overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

  return {
    "status": overall,
    "db": db_status,
    "redis": redis_status,
  }
