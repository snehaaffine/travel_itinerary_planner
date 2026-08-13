from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import LLMProvider, Settings
from app.llm.clients.nvidia import NvidiaChatModel


def get_llm_client(settings: Settings) -> BaseChatModel:
  """Single swap point for LLM provider selection (Section 8)."""
  if settings.llm_provider == LLMProvider.NVIDIA:
    return NvidiaChatModel(settings)
  return ChatAnthropic(
    model=settings.anthropic_model,
    api_key=settings.anthropic_api_key,
  )
