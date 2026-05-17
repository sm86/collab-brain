from __future__ import annotations

import os
import subprocess
import threading


TOOLS = (
    "collab-router:ask_partner_brain",
    "collab-router:ask_partner_brains",
)
TIMEOUT_SECONDS = 20
_LOCK = threading.Lock()


def _is_garry() -> bool:
    return os.environ.get("PARTNER_NAME", "").strip().lower() == "garry"


def _run_hermes(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hermes", *args],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )


def _tool_status() -> tuple[str, str]:
    result = _run_hermes(["tools", "list", "--platform", "telegram"])
    if result.returncode != 0:
        return "error", "Could not read company brain access status."

    output = result.stdout
    if "collab-router" not in output:
        return "missing", "collab-router is not configured for Garry."
    if "all tools enabled" in output:
        return "on", "Company brain access is on for Telegram."
    if "ask_partner_brain" in output or "ask_partner_brains" in output:
        return "off", "Company brain access is off for Telegram."
    return "partial", "Company brain access is partially configured for Telegram."


def _set_enabled(enabled: bool) -> str:
    verb = "enable" if enabled else "disable"
    with _LOCK:
        result = _run_hermes(["tools", verb, "--platform", "telegram", *TOOLS])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if "collab-router" in detail and "not" in detail.lower():
            return "collab-router is not configured for Garry. Register the MCP server first."
        return "Could not update company brain access. Check Garry container logs."

    state = "on" if enabled else "off"
    reset_text = "with" if enabled else "without"
    return (
        f"Company brain access is {state} for Telegram.\n"
        f"Send /reset to start a fresh session {reset_text} company brain access."
    )


def _handle_collab(raw_args: str = "") -> str:
    if not _is_garry():
        return "/collab is only enabled for Garry in this demo."

    command = (raw_args or "").strip().lower()
    if not command:
        command = "status"

    if command == "status":
        _state, message = _tool_status()
        return message
    if command == "on":
        return _set_enabled(True)
    if command == "off":
        return _set_enabled(False)
    return "Usage: /collab on | off | status"


def register(ctx) -> None:
    ctx.register_command(
        "collab",
        handler=_handle_collab,
        description="Turn company brain access on/off.",
        args_hint="[on|off|status]",
    )
