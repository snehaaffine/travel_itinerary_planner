from langchain_anthropic import ChatAnthropic

from app.config import Settings


def create_anthropic_client(settings: Settings) -> ChatAnthropic:
  return ChatAnthropic(
    model=settings.anthropic_model,
    api_key=settings.anthropic_api_key,
  )
