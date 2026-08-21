from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    NVIDIA = "nvidia"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg://travel_planner:travel_planner@localhost:5433/travel_planner"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Runtime
    app_env: str = "development"

    # Auth
    app_api_token: str = "dev-app-token"
    session_secret: str = "dev-session-secret-change-in-production"
    session_cookie_name: str = "trip_session"
    session_cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # LLM
    llm_provider: LLMProvider = LLMProvider.ANTHROPIC
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    nvidia_api_key: str | None = None
    nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_timeout_seconds: float = 300.0
    nvidia_max_tokens: int = 8192

    # External APIs (wired for later phases)
    geoapify_api_key: str | None = None
    tavily_api_key: str | None = None
    cambai_api_key: str | None = None
    gemini_api_key: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def rate_limits_enabled(self) -> bool:
        from app.constants import PROD_ENVIRONMENTS

        return self.app_env.strip().lower() in PROD_ENVIRONMENTS


def get_settings() -> Settings:
    return Settings()
