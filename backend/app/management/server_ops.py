from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import REPO_ROOT, get_settings

MAX_OUTPUT_BYTES = 200 * 1024
COMMAND_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class ServerOpsCommand:
    command_id: str
    argv: tuple[str, ...]
    description: str


def _python_health_command() -> tuple[str, ...]:
    return (
        sys.executable,
        "-c",
        "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=10).read().decode('utf-8', 'replace'))",
    )


def _update_script_command() -> tuple[str, ...]:
    return ("bash", str(REPO_ROOT / "deploy" / "management-v1.7.4" / "update-carbonrag.sh"))


ALLOWED_COMMANDS: dict[str, ServerOpsCommand] = {
    "service_status": ServerOpsCommand(
        command_id="service_status",
        argv=("systemctl", "status", "carbonrag", "--no-pager"),
        description="查看 carbonrag systemd 服务状态",
    ),
    "recent_logs": ServerOpsCommand(
        command_id="recent_logs",
        argv=("journalctl", "-u", "carbonrag", "-n", "200", "--no-pager"),
        description="查看 carbonrag 最近 200 行日志",
    ),
    "healthz": ServerOpsCommand(
        command_id="healthz",
        argv=_python_health_command(),
        description="调用本机后端 /healthz",
    ),
    "git_head": ServerOpsCommand(
        command_id="git_head",
        argv=("git", "rev-parse", "HEAD"),
        description="查看当前部署 Git commit",
    ),
    "update_carbonrag": ServerOpsCommand(
        command_id="update_carbonrag",
        argv=_update_script_command(),
        description="运行受控更新脚本",
    ),
    "restart_service": ServerOpsCommand(
        command_id="restart_service",
        argv=("systemctl", "restart", "carbonrag"),
        description="重启 carbonrag 服务",
    ),
}


def ensure_server_ops_enabled() -> None:
    if not bool(getattr(get_settings(), "enable_web_ssh_terminal", False)):
        raise HTTPException(status_code=404, detail="Controlled server ops panel is disabled.")


def list_allowed_server_ops_commands() -> list[dict[str, str]]:
    return [
        {"command_id": command.command_id, "description": command.description}
        for command in ALLOWED_COMMANDS.values()
    ]


def run_allowed_server_ops_command(command_id: str) -> dict[str, object]:
    ensure_server_ops_enabled()
    command = ALLOWED_COMMANDS.get(command_id)
    if command is None:
        raise HTTPException(status_code=400, detail="Unsupported server ops command.")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command.argv),
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
        stdout, stdout_truncated = _truncate_output(completed.stdout or "")
        stderr, stderr_truncated = _truncate_output(completed.stderr or "")
        return {
            "command_id": command_id,
            "status": "completed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "truncated": stdout_truncated or stderr_truncated,
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _truncate_output(exc.stdout or "")
        stderr, stderr_truncated = _truncate_output(exc.stderr or "")
        return {
            "command_id": command_id,
            "status": "timeout",
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "truncated": stdout_truncated or stderr_truncated,
        }


def _truncate_output(value: str) -> tuple[str, bool]:
    encoded = value.encode("utf-8", "replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return value, False
    truncated = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", "replace")
    return truncated + "\n...[output truncated by CarbonRag server ops safety limit]", True
