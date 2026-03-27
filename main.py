"""Router & Memory Bot — Gradio UI (default) or CLI (--cli)."""

from __future__ import annotations

import argparse
import sys

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

import gradio as gr
from dotenv import load_dotenv

import memory
from router import get_llm_client, run_turn


def _messages_to_chatbot_pairs(msgs: list[dict]) -> list[list[str]]:
    """Gradio 4 Chatbot: list of [user, assistant] turns (use '' if no reply yet)."""
    pairs: list[list[str]] = []
    i = 0
    while i < len(msgs):
        m = msgs[i]
        if m.get("role") != "user":
            i += 1
            continue
        user_text = str(m.get("content", ""))
        assistant_text = ""
        if i + 1 < len(msgs) and msgs[i + 1].get("role") == "assistant":
            assistant_text = str(msgs[i + 1].get("content", ""))
            i += 2
        else:
            i += 1
        pairs.append([user_text, assistant_text])
    return pairs


def launch_gradio() -> None:
    load_dotenv()
    client, model = get_llm_client()
    default_md = (
        f"**Router & Memory Bot** · מודל: `{model}` · היסטוריה נשמרת ל־`history.json`"
    )

    def initial_load() -> tuple[list[list[str]], list[dict], dict]:
        msgs = memory.load_messages()
        banner = (
            "**ברוך שובך** — המשך השיחה נטען מ־`history.json`."
            if memory.history_exists()
            else default_md
        )
        return _messages_to_chatbot_pairs(msgs), msgs, gr.update(value=banner)

    def submit(
        message: str, state_messages: list[dict] | None
    ) -> tuple[str, list[list[str]], list[dict], dict]:
        msg = (message or "").strip()
        st = list(state_messages or [])
        if not msg:
            return "", _messages_to_chatbot_pairs(st), st, gr.update()

        if msg == "/reset":
            memory.clear_history_file()
            return "", [], [], gr.update(value=default_md)

        try:
            new_state, _ = run_turn(client, model, st, msg)
            memory.save_messages(new_state)
            return "", _messages_to_chatbot_pairs(new_state), new_state, gr.update()
        except Exception as e:
            raise gr.Error(f"שגיאה: {e}") from e

    def do_reset() -> tuple[list[list[str]], list[dict], dict]:
        memory.clear_history_file()
        return [], [], gr.update(value=default_md)

    initial_msgs = memory.load_messages()
    initial_pairs = _messages_to_chatbot_pairs(initial_msgs)

    with gr.Blocks(title="Router & Memory Bot") as demo:
        banner = gr.Markdown(value=default_md)
        chatbot = gr.Chatbot(
            label="שיחה",
            height=440,
            value=initial_pairs,
        )
        state = gr.State(initial_msgs)
        inp = gr.Textbox(
            label="הודעה",
            placeholder="למשל: כמה חם בתל אביב?  ·  /reset לאיפוס",
            lines=1,
        )
        with gr.Row():
            send = gr.Button("שלח", variant="primary")
            reset = gr.Button("איפוס זיכרון")
        gr.Markdown(
            "פקודת **`/reset`** או הכפתור מוחקים את `history.json` ומתחילים שיחה חדשה."
        )

        demo.load(initial_load, outputs=[chatbot, state, banner])
        inp.submit(
            submit,
            inputs=[inp, state],
            outputs=[inp, chatbot, state, banner],
        )
        send.click(
            submit,
            inputs=[inp, state],
            outputs=[inp, chatbot, state, banner],
        )
        reset.click(do_reset, outputs=[chatbot, state, banner])

    demo.launch()


def run_cli() -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Router & Memory Bot")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run terminal chat instead of Gradio",
    )
    args = parser.parse_args()
    if args.cli:
        run_cli()
    else:
        launch_gradio()


if __name__ == "__main__":
    main()
    sys.exit(0)
