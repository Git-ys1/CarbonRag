from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import os
import shlex
import signal
import subprocess
import time
from typing import Any

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from app.core.config import REPO_ROOT, get_settings

if os.name != "nt":
    import pty
else:  # pragma: no cover - Windows can import the module but cannot run PTY sessions.
    pty = None  # type: ignore[assignment]

MAX_TERMINAL_INPUT_BYTES = 4096
MAX_TERMINAL_OUTPUT_CHUNK_BYTES = 8192
COMMAND_AUDIT_MAX_CHARS = 240


def ensure_web_ssh_enabled() -> None:
    if not getattr(get_settings(), "enable_web_ssh_terminal", False):
        raise HTTPException(status_code=404, detail="Web SSH terminal is disabled.")


def get_terminal_status() -> dict[str, bool | str | int]:
    settings = get_settings()
    enabled = bool(getattr(settings, "enable_web_ssh_terminal", False))
    return {
        "enabled": enabled,
        "mode": _terminal_mode(enabled),
        "status": "ready" if enabled else "disabled-placeholder",
        "command_preview": _command_preview(settings.web_ssh_command),
        "max_session_seconds": int(settings.web_ssh_max_session_seconds),
    }


async def run_terminal_session(
    websocket: WebSocket,
    *,
    audit_input: Callable[[str], None] | None = None,
) -> None:
    ensure_web_ssh_enabled()
    if os.name == "nt" or pty is None:
        await _run_pipe_terminal_session(websocket, audit_input=audit_input)
        return

    await _run_pty_terminal_session(websocket, audit_input=audit_input)


async def _run_pty_terminal_session(
    websocket: WebSocket,
    *,
    audit_input: Callable[[str], None] | None = None,
) -> None:
    settings = get_settings()
    argv = _terminal_argv(settings.web_ssh_command)
    started_at = time.monotonic()
    master_fd, slave_fd = pty.openpty()
    process: subprocess.Popen[bytes] | None = None
    input_buffer = ""
    try:
        process = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(REPO_ROOT),
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave_fd)
        await websocket.send_json(
            {
                "type": "status",
                "status": "started",
                "command": _command_preview(settings.web_ssh_command),
            }
        )

        async def pump_output() -> None:
            while process and process.poll() is None:
                try:
                    data = await asyncio.to_thread(os.read, master_fd, MAX_TERMINAL_OUTPUT_CHUNK_BYTES)
                except OSError:
                    break
                if not data:
                    break
                await websocket.send_json({"type": "output", "data": data.decode("utf-8", "replace")})

        async def pump_input() -> None:
            nonlocal input_buffer
            while process and process.poll() is None:
                if time.monotonic() - started_at > int(settings.web_ssh_max_session_seconds):
                    await websocket.send_json({"type": "error", "detail": "Web SSH terminal session expired."})
                    break
                raw = await websocket.receive_text()
                if len(raw.encode("utf-8", "replace")) > MAX_TERMINAL_INPUT_BYTES:
                    await websocket.send_json({"type": "error", "detail": "Terminal input message is too large."})
                    continue
                message = _parse_terminal_message(raw)
                message_type = message.get("type")
                if message_type == "input":
                    value = str(message.get("data") or "")
                    os.write(master_fd, value.encode("utf-8", "replace"))
                    input_buffer = _audit_terminal_input(input_buffer, value, audit_input)
                elif message_type == "resize":
                    # Resize is accepted for future xterm integration; current plain UI is line-oriented.
                    continue
                elif message_type == "close":
                    break
                else:
                    await websocket.send_json({"type": "error", "detail": "Unsupported terminal message type."})

        output_task = asyncio.create_task(pump_output())
        input_task = asyncio.create_task(pump_input())
        done, pending = await asyncio.wait({output_task, input_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    except WebSocketDisconnect:
        return
    except OSError as exc:
        await websocket.send_json({"type": "error", "detail": f"Terminal process error: {exc}"})
    finally:
        if process and process.poll() is None:
            _terminate_process(process)
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            await websocket.send_json({"type": "status", "status": "closed"})
        except Exception:
            pass


async def _run_pipe_terminal_session(
    websocket: WebSocket,
    *,
    audit_input: Callable[[str], None] | None = None,
) -> None:
    settings = get_settings()
    argv = _terminal_argv(settings.web_ssh_command)
    started_at = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    input_buffer = ""
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            close_fds=True,
        )
        await websocket.send_json(
            {
                "type": "status",
                "status": "started",
                "command": _command_preview(settings.web_ssh_command),
                "mode": "pipe-proxy",
            }
        )

        async def pump_output() -> None:
            assert process is not None
            assert process.stdout is not None
            while process.poll() is None:
                try:
                    data = await asyncio.to_thread(process.stdout.read, 1)
                except OSError:
                    break
                if not data:
                    break
                await websocket.send_json({"type": "output", "data": data.decode("utf-8", "replace")})

        async def pump_input() -> None:
            nonlocal input_buffer
            assert process is not None
            assert process.stdin is not None
            while process.poll() is None:
                if time.monotonic() - started_at > int(settings.web_ssh_max_session_seconds):
                    await websocket.send_json({"type": "error", "detail": "Web SSH terminal session expired."})
                    break
                raw = await websocket.receive_text()
                if len(raw.encode("utf-8", "replace")) > MAX_TERMINAL_INPUT_BYTES:
                    await websocket.send_json({"type": "error", "detail": "Terminal input message is too large."})
                    continue
                message = _parse_terminal_message(raw)
                message_type = message.get("type")
                if message_type == "input":
                    value = str(message.get("data") or "")
                    try:
                        process.stdin.write(value.encode("utf-8", "replace"))
                        process.stdin.flush()
                    except OSError:
                        break
                    input_buffer = _audit_terminal_input(input_buffer, value, audit_input)
                elif message_type == "resize":
                    continue
                elif message_type == "close":
                    break
                else:
                    await websocket.send_json({"type": "error", "detail": "Unsupported terminal message type."})

        output_task = asyncio.create_task(pump_output())
        input_task = asyncio.create_task(pump_input())
        done, pending = await asyncio.wait({output_task, input_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    except WebSocketDisconnect:
        return
    except OSError as exc:
        await websocket.send_json({"type": "error", "detail": f"Terminal process error: {exc}"})
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            await websocket.send_json({"type": "status", "status": "closed"})
        except Exception:
            pass


def _terminal_mode(enabled: bool) -> str:
    if not enabled:
        return "disabled-placeholder"
    return "pipe-proxy" if os.name == "nt" else "pty-proxy"


def _terminal_argv(command: str) -> list[str]:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="WEB_SSH_COMMAND is invalid.") from exc
    if not argv:
        raise HTTPException(status_code=500, detail="WEB_SSH_COMMAND is empty.")
    return argv


def _command_preview(command: str) -> str:
    return " ".join(shlex.split(command)) if command.strip() else ""


def _parse_terminal_message(raw: str) -> dict[str, Any]:
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return {"type": "input", "data": raw}
    return message if isinstance(message, dict) else {"type": "input", "data": raw}


def _audit_terminal_input(
    input_buffer: str,
    value: str,
    audit_input: Callable[[str], None] | None,
) -> str:
    if audit_input is None:
        return ""
    next_buffer = input_buffer
    for char in value:
        if char in {"\r", "\n"}:
            command = next_buffer.strip()
            if command:
                audit_input(_redact_command_for_audit(command))
            next_buffer = ""
        elif char == "\x7f":
            next_buffer = next_buffer[:-1]
        elif char.isprintable() or char in {"\t"}:
            next_buffer += char
            if len(next_buffer) > COMMAND_AUDIT_MAX_CHARS:
                next_buffer = next_buffer[-COMMAND_AUDIT_MAX_CHARS:]
    return next_buffer


def _redact_command_for_audit(command: str) -> str:
    lowered = command.lower()
    if any(token in lowered for token in ("password", "passwd", "token", "secret", "apikey", "api_key", "key=")):
        return "[redacted sensitive terminal input]"
    if len(command) > COMMAND_AUDIT_MAX_CHARS:
        return command[:COMMAND_AUDIT_MAX_CHARS] + "...[truncated]"
    return command


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except Exception:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            process.kill()
