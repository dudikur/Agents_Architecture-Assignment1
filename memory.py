"""Persistent chat history in history.json (assignment Part B)."""

from __future__ import annotations

import json
from pathlib import Path

HISTORY_PATH = Path(__file__).resolve().parent / "history.json"


def history_exists() -> bool:
    return HISTORY_PATH.is_file()


def load_messages() -> list[dict]:
    if not HISTORY_PATH.is_file():
        return []
    raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    messages = raw.get("messages", [])
    if not isinstance(messages, list):
        return []
    return messages


def save_messages(messages: list[dict]) -> None:
    if not messages:
        clear_history_file()
        return
    HISTORY_PATH.write_text(
        json.dumps({"messages": messages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_history_file() -> None:
    if HISTORY_PATH.is_file():
        HISTORY_PATH.unlink()
