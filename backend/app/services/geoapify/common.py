from app.config import Settings, get_settings


class GeoapifyError(Exception):
    pass


def require_key(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.geoapify_api_key:
        raise GeoapifyError("GEOAPIFY_API_KEY is not configured")
    return settings.geoapify_api_key
