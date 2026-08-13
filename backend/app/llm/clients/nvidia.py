import json
from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
  AIMessage,
  BaseMessage,
  HumanMessage,
  SystemMessage,
  ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult

from app.config import Settings


def _message_to_api_format(message: BaseMessage) -> dict[str, Any]:
  if isinstance(message, SystemMessage):
    return {"role": "system", "content": message.content}

  if isinstance(message, HumanMessage):
    return {"role": "user", "content": message.content}

  if isinstance(message, AIMessage):
    payload: dict[str, Any] = {
      "role": "assistant",
      "content": message.content or None,
    }
    if message.tool_calls:
      payload["tool_calls"] = [
        {
          "id": tool_call["id"],
          "type": "function",
          "function": {
            "name": tool_call["name"],
            "arguments": json.dumps(tool_call["args"]),
          },
        }
        for tool_call in message.tool_calls
      ]
    return payload

  if isinstance(message, ToolMessage):
    return {
      "role": "tool",
      "tool_call_id": message.tool_call_id,
      "content": message.content,
    }

  raise TypeError(f"Unsupported message type: {type(message)}")


def _parse_api_message(message: dict[str, Any]) -> AIMessage:
  content = message.get("content") or ""
  tool_calls: list[dict[str, Any]] = []

  for tool_call in message.get("tool_calls") or []:
    function = tool_call.get("function", {})
    raw_args = function.get("arguments") or "{}"
    try:
      args = json.loads(raw_args)
    except json.JSONDecodeError:
      args = {"raw_arguments": raw_args}

    tool_calls.append(
      {
        "id": tool_call["id"],
        "name": function.get("name", ""),
        "args": args,
      }
    )

  return AIMessage(content=content, tool_calls=tool_calls)


class NvidiaChatModel(BaseChatModel):
  """LangChain-compatible wrapper for NVIDIA Nemotron API."""

  model: str
  api_key: str | None
  base_url: str
  timeout_seconds: float

  def __init__(self, settings: Settings) -> None:
    super().__init__(
      model=settings.nvidia_model,
      api_key=settings.nvidia_api_key,
      base_url=settings.nvidia_base_url,
      timeout_seconds=settings.nvidia_timeout_seconds,
    )

  @property
  def _llm_type(self) -> str:
    return "nvidia-nemotron"

  def _generate(
    self,
    messages: list[BaseMessage],
    stop: list[str] | None = None,
    run_manager: Any = None,
    **kwargs: Any,
  ) -> ChatResult:
    if not self.api_key:
      raise ValueError("NVIDIA_API_KEY is required when LLM_PROVIDER=nvidia")

    payload: dict[str, Any] = {
      "model": self.model,
      "messages": [_message_to_api_format(message) for message in messages],
      "max_tokens": kwargs.get("max_tokens", 1024),
    }

    if "tools" in kwargs:
      payload["tools"] = kwargs["tools"]
    if "tool_choice" in kwargs:
      payload["tool_choice"] = kwargs["tool_choice"]
    if "reasoning_effort" in kwargs:
      payload["reasoning_effort"] = kwargs["reasoning_effort"]
    elif "tools" in kwargs:
      payload["reasoning_effort"] = "none"

    timeout_seconds = kwargs.get("timeout_seconds", self.timeout_seconds)
    timeout = httpx.Timeout(timeout_seconds)

    try:
      with httpx.Client(timeout=timeout) as client:
        response = client.post(
          f"{self.base_url}/chat/completions",
          headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
          },
          json=payload,
        )
    except httpx.TimeoutException as exc:
      raise ValueError(
        f"NVIDIA API timed out after {timeout_seconds:.0f}s for model '{self.model}'. "
        "Nemotron Ultra is slow — try increasing NVIDIA_TIMEOUT_SECONDS in .env, "
        "or switch to a faster model such as nvidia/nemotron-3.5-lightning-30b-a3b."
      ) from exc

    if response.is_error:
      detail = response.text.strip() or response.reason_phrase
      raise ValueError(
        f"NVIDIA API error {response.status_code} for model '{self.model}': {detail}"
      ) from None
    data = response.json()

    api_message = data["choices"][0]["message"]
    ai_message = _parse_api_message(api_message)
    return ChatResult(generations=[ChatGeneration(message=ai_message)])
