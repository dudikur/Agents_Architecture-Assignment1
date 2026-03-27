"""Assignment tool functions: weather (live API), math (deterministic), FX (live Frankfurter API)."""

from __future__ import annotations

import ast
import operator
import requests

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_FRANKFURTER_LATEST = "https://api.frankfurter.app/latest"

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


_FX_ALIASES: dict[str, str] = {
    "DOLLAR": "USD",
    "דולר": "USD",
    "EURO": "EUR",
    "יורו": "EUR",
    "POUND": "GBP",
    "FUNT": "GBP",
    "ליש": "GBP",
}
_FX_SNIFF_ORDER = ("USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY")


def _normalize_fx_code(currencyCode: str) -> str:
    raw = (currencyCode or "").strip()
    if not raw:
        return ""
    if raw in _FX_ALIASES:
        return _FX_ALIASES[raw]
    upper = raw.upper()
    if upper in _FX_ALIASES:
        return _FX_ALIASES[upper]
    if len(upper) == 3 and upper.isalpha():
        return upper
    for iso in _FX_SNIFF_ORDER:
        if iso in upper:
            return iso
    return upper[:3].upper() if len(upper) >= 3 else upper


def getExchangeRate(currencyCode: str) -> str:
    """Live rate: units of ILS per 1 unit of foreign currency (Frankfurter, no API key)."""
    raw_in = (currencyCode or "").strip()
    if "שקל" in raw_in or "ש״ח" in raw_in:
        return "המטבע המקומי הוא השקל; בחרו מטבע זר להמרה (למשל USD, EUR)."

    code = _normalize_fx_code(raw_in)
    if not code or len(code) != 3 or not code.isalpha():
        return (
            f"לא זוהה קוד מטבע תקף ב-{currencyCode!r}. "
            "נסו קוד ISO בן שלוש אותיות, למשל USD, EUR, GBP."
        )

    if code == "ILS":
        return "המטבע המקומי הוא השקל; בחרו מטבע זר להמרה (למשל USD, EUR)."

    try:
        r = requests.get(
            _FRANKFURTER_LATEST,
            params={"from": code, "to": "ILS"},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return (
            "לא ניתן להשיג שער מזמן שירות המטבעות. נסו שוב מאוחר יותר "
            "(USD, EUR, GBP)."
        )

    rates = data.get("rates") if isinstance(data, dict) else None
    ils_rate = rates.get("ILS") if isinstance(rates, dict) else None
    if ils_rate is None:
        return (
            f"המטבע {code} לא נתמך או אין נתון להמרה ל-ILS. "
            "נסו למשל USD, EUR, GBP, JPY."
        )

    as_of = data.get("date", "?")
    return (
        f"שער {code} (חי, Frankfurter): 1 {code} = {ils_rate:g} ש״ח "
        f"(נכון לתאריך {as_of})."
    )


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
