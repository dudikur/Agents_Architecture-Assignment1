"""Assignment tool functions: weather (live API), math (deterministic), FX (static)."""

from __future__ import annotations

import ast
import operator
import requests

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO-ish descriptions in Hebrew for current weather_code from Open-Meteo
_WMO_HE: dict[int, str] = {
    0: "בהיר",
    1: "ברור ברובו",
    2: "מעונן חלקית",
    3: "מעונן",
    45: "ערפל",
    48: "ערפל קפוא",
    51: "טפטוף קל",
    53: "טפטוף",
    55: "טפטוף כבד",
    56: "טפטוף קפוא",
    57: "טפטוף קפוא כבד",
    61: "גשם קל",
    63: "גשם",
    65: "גשם כבד",
    66: "גשם מקורר",
    67: "גשם מקורר כבד",
    71: "שלג קל",
    73: "שלג",
    75: "שלג כבד",
    77: "גרגירי שלג",
    80: "ממטרים קלים",
    81: "ממטרים",
    82: "ממטרים כבדים",
    85: "ממטרי שלג",
    86: "ממטרי שלג כבדים",
    95: "סופת רעמים",
    96: "סופת רעמים עם ברד קל",
    99: "סופת רעמים עם ברד כבד",
}


def _wmo_label(code: int | None) -> str:
    if code is None:
        return "לא ידוע"
    return _WMO_HE.get(int(code), "תנאים מעורבבים")


_ALLOWED_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_ALLOWED_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("רק מספרים מותרים בביטוי")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("חלוקה באפס")
        return float(_ALLOWED_BINOPS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return float(_ALLOWED_UNARY[type(node.op)](_eval_ast(node.operand)))
    raise ValueError("תו או פעולה לא חוקית בביטוי")


def calculateMath(expression: str) -> str:
    """Evaluate a numeric expression deterministically (no LLM)."""
    text = (expression or "").strip()
    if not text:
        return "לא התקבל ביטוי מתמטי."
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return "ביטוי מתמטי לא תקין."
    try:
        value = _eval_ast(tree.body)
    except ValueError as e:
        return str(e)
    if value == int(value):
        return str(int(value))
    return f"{value:.6g}"


_STATIC_RATES_TO_ILS = {
    "USD": 3.75,
    "EUR": 4.05,
    "GBP": 4.80,
    "JPY": 0.025,
    "CAD": 2.75,
    "CHF": 4.20,
}


def getExchangeRate(currencyCode: str) -> str:
    """Static representative rate → ILS (assignment allows dictionary)."""
    code = (currencyCode or "").strip().upper()
    aliases = {"DOLLAR": "USD", "דולר": "USD", "EURO": "EUR", "יורו": "EUR"}
    if code in aliases:
        code = aliases[code]
    if len(code) != 3 and code not in _STATIC_RATES_TO_ILS:
        for k in _STATIC_RATES_TO_ILS:
            if k in code.upper():
                code = k
                break
    rate = _STATIC_RATES_TO_ILS.get(code)
    if rate is None:
        return f"אין נתון סטטי לקוד המטבע {currencyCode!r}. נתמוך ב: {', '.join(sorted(_STATIC_RATES_TO_ILS))}."
    return f"שער ה{code} היציג הוא {rate} ש״ח (נתון לדוגמה סטטי להגשה)."


def getWeather(city: str) -> str:
    """Live forecast via Open-Meteo (no API key)."""
    name = (city or "").strip()
    if not name:
        return "לא צוינה עיר."

    geo = requests.get(
        _GEOCODE_URL,
        params={"name": name, "count": 1, "language": "he"},
        timeout=12,
    )
    geo.raise_for_status()
    gdata = geo.json()
    results = gdata.get("results") or []
    if not results:
        return f"לא נמצאה עיר: {name}"

    lat = results[0]["latitude"]
    lon = results[0]["longitude"]
    label = results[0].get("name") or name

    fc = requests.get(
        _FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "timezone": "Asia/Jerusalem",
        },
        timeout=12,
    )
    fc.raise_for_status()
    cur = fc.json().get("current") or {}
    temp = cur.get("temperature_2m")
    code = cur.get("weather_code")
    desc = _wmo_label(code)

    if temp is None:
        return f"לא התקבל מזג אוויר ל-{label}."
    return f"{label}: {temp:g} מעלות, {desc}."
