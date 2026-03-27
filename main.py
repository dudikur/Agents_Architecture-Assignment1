"""Router & Memory Bot — CLI entry (Assignment 1)."""

from __future__ import annotations

import sys

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

from dotenv import load_dotenv

import memory
from router import get_llm_client, run_turn


def main() -> None:
    load_dotenv()
    had_history = memory.history_exists()
    messages = memory.load_messages()
    if had_history:
        print("ברוך שובך")

    client, model = get_llm_client()
    print("סוכן צ'אט: הקלד הודעה, /reset לאיפוס זיכרון, /exit ליציאה.")
    print(f"(מודל: {model})\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line == "/exit":
            break
        if line == "/reset":
            memory.clear_history_file()
            messages = []
            print("היסטוריה נמחקה. שיחה חדשה.")
            continue

        try:
            messages, reply = run_turn(client, model, messages, line)
        except Exception as e:
            print(f"שגיאה: {e}")
            continue
        print(reply)
        memory.save_messages(messages)

    memory.save_messages(messages)


if __name__ == "__main__":
    main()
    sys.exit(0)
