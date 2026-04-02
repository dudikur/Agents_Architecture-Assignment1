# Router & Memory Bot (תרגיל 1)

סוכן צ'אט עם **ניתוב כוונות** (Router), **ארבע יכולות** (מזג אוויר, חישוב, שער מטבע, שיחה כללית), ו**זיכרון** בקובץ `history.json`.

## What is in this project

| File | Purpose |
|------|---------|
| [`main.py`](main.py) | Entry point: **Gradio** web UI by default, or terminal chat with `--cli`. |
| [`router.py`](router.py) | LLM classification → JSON `{ "tool", "arguments" }`, then dispatches to tools or general chat. |
| [`tools_catalog.py`](tools_catalog.py) | OpenAI-style tool JSON specs + `TOOL_REGISTRY` (map dispatch, no long if/elif). |
| [`tools.py`](tools.py) | Implementations: **Open-Meteo** (weather), safe **AST** math, **Frankfurter** (live FX vs ILS). |
| [`memory.py`](memory.py) | Load / save / clear `history.json`. |
| [`requirements.txt`](requirements.txt) | Python dependencies (including Gradio 4.x + pinned Pydantic for compatibility). |
| [`.env.example`](.env.example) | Template for API keys (copy to `.env`). |
| [`execution_log.txt`](execution_log.txt) | Template + checklist for **submission** (paste a real session transcript). |
| `תרגיל מספר 1.docx` | Original assignment (Hebrew). |

**External services (no keys where noted):**

- **LLM:** Gemini, Groq, or OpenAI (see below).
- **Weather:** Open-Meteo (no API key).
- **Exchange rates:** Frankfurter (no API key; daily rates).

---

## How to start

### 1. Python environment

Use Python 3.9+ (Gradio 4.x in this repo targets 3.9; Gradio 5 needs 3.10+).

```powershell
cd "your path\Agents_Architecture-Assignment1"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If `Activate.ps1` is blocked, run commands with `.\.venv\Scripts\python.exe` directly.

### 2. Environment variables (`.env`)

1. Copy the example file:

   ```powershell
   copy .env.example .env
   ```

2. Open `.env` and set **at least one** LLM key (the app checks in this order):

   | Variable | Notes |
   |----------|--------|
   | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | **Preferred** in this project. Get a key at [Google AI Studio](https://aistudio.google.com/apikey). Optional: `GEMINI_MODEL` (default `gemini-2.5-flash`). |
   | `GROQ_API_KEY` | Free tier at [Groq Console](https://console.groq.com). Optional: `GROQ_MODEL`. |
   | `OPENAI_API_KEY` | If you use OpenAI directly. Optional: `OPENAI_MODEL`. |

3. **Security:** Never commit `.env` or paste keys into public repos. `.gitignore` already excludes `.env` and `history.json`.

### 3. Run the app

**Web UI (Gradio)** — default:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python main.py
```

A browser window opens; chat is saved to `history.json` after each turn.

**Terminal only:**

```powershell
python main.py --cli
```

Commands in both modes:

- `/reset` — deletes `history.json` and starts a clean session (Gradio also has an **איפוס זיכרון** button).
- In CLI only: `/exit` — quit (and save).

On Windows, UTF-8 output for Hebrew is easiest with **Windows Terminal** and `PYTHONIOENCODING=utf-8` as above.

---

## `execution_log.txt` — what it is and how to use it

This file is meant for **assignment submission**: a **text transcript** (or you can add screenshots separately) that proves the bot behaves as required.

### What the template contains

- **Comments (`# …`)** — checklist: install deps, configure `.env`, run the app, cover all scenarios.
- **Sample session layout** — shows the **order** of prompts you should run once with a **real** API key, then **replace** the placeholders with your actual bot answers.

### What final log demonstrate

1. **Weather** — e.g. Tel Aviv temperature (routed to `getWeather` / Open-Meteo).
2. **FX** — e.g. dollar vs shekel (routed to `getExchangeRate` / Frankfurter; **live** rate + date in the reply).
3. **Math** — e.g. “150 ועוד 20” → deterministic answer (e.g. `170`), not from the LLM.
4. **General chat** — any open question answered via `generalChat`.
5. **Persistence** — quit, run `python main.py` again: you should see **ברוך שובך** (if `history.json` existed) and a follow-up that shows the model **remembers** prior context (loaded from `history.json`).

### Tips

- If you use **Gradio**, you can copy the visible chat into `execution_log.txt`, or run **`python main.py --cli`** once to capture a clean terminal log.
- Remove or rewrite outdated comment lines in the template (e.g. references to “static” FX) so the log matches the **current** implementation.
- Before zipping for submission, ensure `.env` is **not** included unless your instructor explicitly asks for it (normally omit).

---

## Troubleshooting

- **Gradio crash on startup (`_SpecialForm` / Pydantic):** Keep `pydantic>=2.0.0,<2.11.0` as in `requirements.txt` and reinstall: `pip install -r requirements.txt`.
- **`huggingface_hub` ImportError with Gradio:** Use `huggingface_hub>=0.23.0,<1.0` as pinned in `requirements.txt`.
- **429 / quota from Gemini:** Try another `GEMINI_MODEL`, wait, or use `GROQ_API_KEY` / `OPENAI_API_KEY` instead.
