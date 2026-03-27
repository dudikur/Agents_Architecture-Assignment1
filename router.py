"""LLM router: classify to JSON {tool, arguments}, dispatch via TOOL_REGISTRY (4_lab4 pattern)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from tools_catalog import (
    FALLBACK_TOOL,
    classifier_instructions,
    invoke_registered_tool,
    normalize_plan,
)

CLASSIFIER_SYSTEM = classifier_instructions()

CHAT_SYSTEM = """You are a helpful bilingual assistant (Hebrew and English).
Answer concisely and clearly. If the user writes in Hebrew, prefer Hebrew unless they ask otherwise."""

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _strip_json_payload(text: str) -> str:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        return m.group(1).strip()
    return text


def _parse_classify(raw: str) -> dict[str, Any]:
    payload = _strip_json_payload(raw)
    return json.loads(payload)


def default_routing() -> dict[str, Any]:
    return {"tool": FALLBACK_TOOL, "arguments": {}}


def get_llm_client() -> tuple[OpenAI, str]:
    load_dotenv()
    gemini = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini:
        base = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return OpenAI(api_key=gemini, base_url=base), model
    groq = os.getenv("GROQ_API_KEY")
    if groq:
        base = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        return OpenAI(api_key=groq, base_url=base), model
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Set GEMINI_API_KEY (or GOOGLE_API_KEY), GROQ_API_KEY, or OPENAI_API_KEY "
            "in .env (see .env.example)."
        )
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return OpenAI(api_key=key), model


def classify(client: OpenAI, model: str, user_text: str) -> dict[str, Any]:
    res = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CLASSIFIER_SYSTEM},
            {"role": "user", "content": user_text},
        ],
        temperature=0,
    )
    raw = res.choices[0].message.content or ""
    try:
        data = _parse_classify(raw)
    except (json.JSONDecodeError, TypeError):
        return default_routing()
    return normalize_plan(data)


def general_chat(
    client: OpenAI,
    model: str,
    history_messages: list[dict],
    user_input: str,
) -> str:
    """Call LLM with system + full stored history + new user message."""
    msgs: list[dict] = [{"role": "system", "content": CHAT_SYSTEM}]
    for m in history_messages:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content is not None:
            msgs.append({"role": role, "content": str(content)})
    msgs.append({"role": "user", "content": user_input})
    res = client.chat.completions.create(
        model=model,
        messages=msgs,
        temperature=0.7,
    )
    return (res.choices[0].message.content or "").strip()


def run_turn(
    client: OpenAI,
    model: str,
    messages: list[dict],
    user_input: str,
) -> tuple[list[dict], str]:
    """
    Classify user_input, append user message + assistant reply to messages.
    Returns (updated_messages, assistant_text).
    """
    plan = classify(client, model, user_input)
    tool = plan["tool"]
    arguments: dict[str, Any] = plan["arguments"]

    messages = list(messages)
    messages.append({"role": "user", "content": user_input})

    if tool == FALLBACK_TOOL:
        prior = messages[:-1]
        reply = general_chat(client, model, prior, user_input)
    else:
        reply = invoke_registered_tool(tool, arguments)

    messages.append({"role": "assistant", "content": reply})
    return messages, reply
