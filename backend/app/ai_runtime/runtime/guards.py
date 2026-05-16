from dataclasses import dataclass
from typing import Iterable

from app.ai_runtime.config import get_ai_runtime_config
from app.ai_runtime.modes import ModeSpec
from app.ai_runtime.schemas.chat import ChatRequest
from app.ai_runtime.tools.registry import ToolRegistry

FORBIDDEN_CAPABILITIES = (
    "shell",
    "arbitrary_file_write",
    "arbitrary_web_fetch",
    "arbitrary_system_call",
)


@dataclass(frozen=True)
class GuardSnapshot:
    mode_name: str
    allowed_tools: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]


def enforce_mode_whitelist(mode_name: str, allowed_modes: Iterable[str]) -> None:
    if mode_name not in set(allowed_modes):
        raise ValueError(f"Mode is not allowed by ai runtime config: {mode_name}")


def enforce_tool_whitelist(
    mode: ModeSpec,
    registry: ToolRegistry,
    tool_names: Iterable[str],
) -> GuardSnapshot:
    available = set(registry.list_tool_names())
    requested = list(tool_names)
    missing = [tool_name for tool_name in requested if tool_name not in available]
    if missing:
        raise KeyError(f"Requested tools are not registered: {', '.join(sorted(missing))}")

    disallowed = [tool_name for tool_name in requested if tool_name not in mode.allowed_tools]
    if disallowed:
        raise PermissionError(
            f"Requested tools are not allowed in mode '{mode.name}': {', '.join(sorted(disallowed))}"
        )

    return GuardSnapshot(
        mode_name=mode.name,
        allowed_tools=mode.allowed_tools,
        forbidden_capabilities=FORBIDDEN_CAPABILITIES,
    )


def enforce_ask_request_constraints(request: ChatRequest) -> None:
    config = get_ai_runtime_config()
    question = request.user_input.strip()
    if request.mode != "ask":
        raise ValueError("当前 ask 入口只允许 ask mode。")
    if not question:
        raise ValueError("问题不能为空。")
    if len(question) > config.ask_max_question_length:
        raise ValueError(f"问题长度不能超过 {config.ask_max_question_length} 个字符。")
    effective_scope = request.payload.get("knowledge_scope_effective", "mixed")
    if effective_scope not in {"public", "private_sample", "mixed"}:
        raise ValueError("当前 ask 入口只支持 public、private_sample 或 mixed。")
