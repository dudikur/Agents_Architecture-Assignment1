"""LLM router: classify intent, dispatch tools, generalChat with full history."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from tools import calculateMath, getExchangeRate, getWeather

CLASSIFIER_SYSTEM = """You classify user messages for an assistant.
Reply with ONLY a JSON object (no markdown, no prose) with keys:
intent, city, expression, currency.
Use null for unused keys.

intent is exactly one of: weather, math, fx, chat.

- weather: temperature, weather forecast, מזג אוויר, חם, קר, גשם — set "city" to the location name.
- math: arithmetic — set "expression" to a safe arithmetic string using digits, + - * / ( ) and . only (e.g. "150+20").
- fx: currency exchange, דולר, יורו, שער, שקלים — set "currency" to ISO code like USD or EUR when possible.
- chat: general conversation or anything else.

If the user writes Hebrew math like "150 ועוד 20", set expression to "150+20"."""


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


def default_intent() -> dict[str, Any]:
    return {"intent": "chat", "city": None, "expression": None, "currency": None}


def get_llm_client() -> tuple[OpenAI, str]:
    load_dotenv()
    gemini = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini:
        base = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        # gemini-1.5-* removed from API; use current stable Flash (see ai.google.dev/gemini-api/docs/models)
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
        return default_intent()
    intent = data.get("intent", "chat")
    if intent not in ("weather", "math", "fx", "chat"):
        intent = "chat"
    return {
        "intent": intent,
        "city": data.get("city"),
        "expression": data.get("expression"),
        "currency": data.get("currency"),
    }


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
    intent = plan["intent"]

    messages = list(messages)
    messages.append({"role": "user", "content": user_input})

    if intent == "weather":
        city = plan.get("city") or ""
        reply = getWeather(str(city))
    elif intent == "math":
        expr = plan.get("expression") or ""
        reply = calculateMath(str(expr))
    elif intent == "fx":
        cur = plan.get("currency") or ""
        reply = getExchangeRate(str(cur))
    else:
        # generalChat: history is messages[:-1] before this user line... 
        # We already appended user; LLM should see prior history without the duplicate user at end.
        prior = messages[:-1]
        reply = general_chat(client, model, prior, user_input)

    messages.append({"role": "assistant", "content": reply})
    return messages, reply
