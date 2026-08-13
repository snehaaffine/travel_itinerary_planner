import redis

from app.config import get_settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
  global _redis_client
  if _redis_client is None:
    settings = get_settings()
    _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
  return _redis_client


def ping_redis() -> bool:
  try:
    return get_redis().ping()
  except redis.RedisError:
    return False
