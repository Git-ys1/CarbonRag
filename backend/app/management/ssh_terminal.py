from fastapi import HTTPException

from app.core.config import get_settings


def ensure_web_ssh_enabled() -> None:
    if not getattr(get_settings(), "enable_web_ssh_terminal", False):
        raise HTTPException(status_code=404, detail="Web SSH terminal is disabled.")


def get_terminal_status() -> dict[str, bool | str]:
    return {
        "enabled": bool(getattr(get_settings(), "enable_web_ssh_terminal", False)),
        "mode": "disabled-placeholder",
    }
