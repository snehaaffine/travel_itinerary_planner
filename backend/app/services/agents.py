from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.config import get_settings
from app.constants import SPECIALIST_AGENT_ROUNDS
from app.llm.provider import get_llm_client


class AgentError(Exception):
    pass


@dataclass
class AgentRun:
    text: str
    messages: list
    llm: Any


def message_text(content: Any) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content or "")


def run_tool_agent(
    *,
    system: str,
    user: str,
    tools: list[BaseTool],
    max_rounds: int = SPECIALIST_AGENT_ROUNDS,
    llm: Any | None = None,
) -> AgentRun:
    """Run an LLM that may call its own tools, then return the final briefing."""
    tool_map = {tool.name: tool for tool in tools}
    client = llm or get_llm_client(get_settings())
    bound = client.bind_tools(tools)
    messages: list = [
        SystemMessage(content=system),
        HumanMessage(content=user),
    ]

    for _ in range(max_rounds):
        result = bound.invoke(messages)
        messages.append(result)
        tool_calls = getattr(result, "tool_calls", None) or []
        if not tool_calls:
            return AgentRun(text=message_text(result.content).strip(), messages=messages, llm=bound)
        for tool_call, output in _invoke_tool_calls(tool_map, tool_calls):
            messages.append(ToolMessage(content=str(output), tool_call_id=tool_call["id"]))

    messages.append(
        HumanMessage(
            content="Do not call tools. Return the final answer now using the tool results."
        )
    )
    result = client.invoke(messages)
    messages.append(result)
    text = message_text(result.content).strip()
    if not text:
        raise AgentError("Agent did not finish after tool calls")
    return AgentRun(text=text, messages=messages, llm=bound)


def _invoke_tool_calls(
    tool_map: dict[str, BaseTool],
    tool_calls: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], str]]:
    def run_one(tool_call: dict[str, Any]) -> tuple[dict[str, Any], str]:
        tool = tool_map.get(tool_call["name"])
        if tool is None:
            return tool_call, f"Unknown tool {tool_call['name']}"
        return tool_call, str(tool.invoke(tool_call.get("args") or {}))

    if len(tool_calls) == 1:
        return [run_one(tool_calls[0])]

    results: dict[int, tuple[dict[str, Any], str]] = {}
    with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
        futures = {pool.submit(run_one, call): index for index, call in enumerate(tool_calls)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [results[index] for index in range(len(tool_calls))]


def run_specialist(
    *,
    name: str,
    system: str,
    task: str,
    tools: list[BaseTool],
    llm_factory: Callable[[], Any] | None = None,
) -> str:
    llm = llm_factory() if llm_factory else None
    run = run_tool_agent(system=system, user=task, tools=tools, llm=llm)
    return f"[{name}]\n{run.text}"
