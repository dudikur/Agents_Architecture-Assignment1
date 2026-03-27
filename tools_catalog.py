"""
Router tools: JSON schemas + registry dispatch (pattern from 1_foundations/4_lab4.ipynb).

Specs mirror OpenAI tools format; dispatch uses a map lookup instead of if/elif.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Any

from tools import calculateMath, getExchangeRate, getWeather

# --- OpenAI-style function definitions (same shape as 4_lab4: name, description, parameters) ---

GET_WEATHER_JSON: dict[str, Any] = {
    "name": "getWeather",
    "description": "Get current weather for a city using a live API. Use for מזג אוויר, temperature, חם, קר, גשם.",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name (Hebrew or English), e.g. תל אביב, Haifa",
            }
        },
        "required": ["city"],
        "additionalProperties": False,
    },
}

CALCULATE_MATH_JSON: dict[str, Any] = {
    "name": "calculateMath",
    "description": (
        "Evaluate a numeric expression with + - * / ( ) and digits only — no LLM math. "
        'Put the expression in "expression", e.g. "150+20".'
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": 'Arithmetic string only, e.g. "50 * 3 / 2" or "150+20"',
            }
        },
        "required": ["expression"],
        "additionalProperties": False,
    },
}

GET_EXCHANGE_RATE_JSON: dict[str, Any] = {
    "name": "getExchangeRate",
    "description": "Representative static FX rate to ILS (שקלים). Use for דולר, יורו, שער, המרה.",
    "parameters": {
        "type": "object",
        "properties": {
            "currencyCode": {
                "type": "string",
                "description": 'ISO code e.g. "USD", "EUR"',
            }
        },
        "required": ["currencyCode"],
        "additionalProperties": False,
    },
}

# For optional native OpenAI/Gemini tool-calling later: [{"type": "function", "function": spec}, ...]
TOOLS_OPENAI_WRAPPED: list[dict[str, Any]] = [
    {"type": "function", "function": GET_WEATHER_JSON},
    {"type": "function", "function": CALCULATE_MATH_JSON},
    {"type": "function", "function": GET_EXCHANGE_RATE_JSON},
]

TOOL_FUNCTION_SPECS: list[dict[str, Any]] = [
    GET_WEATHER_JSON,
    CALCULATE_MATH_JSON,
    GET_EXCHANGE_RATE_JSON,
]

# Registry: exact Python / JSON tool name -> implementation (4_lab4 style: globals()[name])
TOOL_REGISTRY: dict[str, Callable[..., str]] = {
    "getWeather": getWeather,
    "calculateMath": calculateMath,
    "getExchangeRate": getExchangeRate,
}

FALLBACK_TOOL = "generalChat"

_SPECS_FOR_PROMPT = json.dumps(TOOL_FUNCTION_SPECS, ensure_ascii=False, indent=2)


def classifier_instructions() -> str:
    """Build router system text from the same JSON specs (single source of truth)."""
    return f"""You route user messages to exactly one tool.

Reply with ONLY a JSON object (no markdown, no other text), shape:
{{"tool": "<exact tool name>", "arguments": {{...}}}}

Allowed tools and JSON Schemas:
{_SPECS_FOR_PROMPT}

Use tool "{FALLBACK_TOOL}" with {{"arguments": {{}}}} for general chat or anything that does not fit the three tools above.

Rules:
- For Hebrew math like "150 ועוד 20", use calculateMath with "expression": "150+20".
- For currency questions, set currencyCode to USD, EUR, etc. when you can infer it."""


def normalize_plan(data: dict[str, Any]) -> dict[str, Any]:
    """Accept legacy classifier output {intent, city, ...} or new {{tool, arguments}}."""
    if "tool" in data:
        tool = str(data["tool"] or FALLBACK_TOOL)
        raw_args = data.get("arguments")
        args = dict(raw_args) if isinstance(raw_args, dict) else {}
        if tool not in TOOL_REGISTRY and tool != FALLBACK_TOOL:
            tool, args = FALLBACK_TOOL, {}
        return {"tool": tool, "arguments": args}

    if "intent" in data:
        intent = str(data.get("intent") or FALLBACK_TOOL).lower()
        legacy_map = {
            "weather": ("getWeather", {"city": str(data.get("city") or "")}),
            "math": ("calculateMath", {"expression": str(data.get("expression") or "")}),
            "fx": ("getExchangeRate", {"currencyCode": str(data.get("currency") or "")}),
            "chat": (FALLBACK_TOOL, {}),
        }
        tool, args = legacy_map.get(intent, (FALLBACK_TOOL, {}))
        return {"tool": tool, "arguments": args}

    return {"tool": FALLBACK_TOOL, "arguments": {}}


def invoke_registered_tool(tool: str, arguments: dict[str, Any]) -> str:
    """Like 4_lab4 handle_tool_calls: look up callable and **arguments (no if/elif per tool)."""
    fn = TOOL_REGISTRY.get(tool)
    if fn is None:
        return ""
    sig = inspect.signature(fn)
    allowed = set(sig.parameters)
    kwargs = {k: v for k, v in arguments.items() if k in allowed}
    return fn(**kwargs)
