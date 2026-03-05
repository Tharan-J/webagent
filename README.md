# Advanced Web Automation & Scraping Agent

A modular, resilient Python agent that combines **Playwright stealth browsing**,
**BeautifulSoup4 HTML parsing**, and **Google Gemini LLM reasoning** to research
any topic from the web with a single command.

---

## Project Structure

```
web_agent/
├── start.py                    # CLI entry point
├── main_agent.py               # Orchestrator
├── requirements.txt
├── .env.example                # Copy → .env and fill in your API key
│
├── config/
│   └── agent_config.py         # All tuneable constants
│
├── models/
│   └── data_models.py          # Pydantic response types
│
├── tools/
│   ├── browser_tool.py         # Playwright stealth wrapper
│   ├── dom_tool.py             # BeautifulSoup extraction utilities
│   ├── interaction_tool.py     # High-level page interactions
│   ├── llm_tool.py             # Gemini LLM wrapper
│   └── logging_tool.py         # Centralised logging
│
├── agents/
│   ├── base_agent.py           # Abstract base with shared utilities
│   ├── navigation_agent.py     # Resilient page navigation (with retries)
│   ├── captcha_agent.py        # CAPTCHA detection & signalling
│   ├── dom_agent.py            # DOM → PageContent extraction
│   ├── content_extraction_agent.py  # DOM + LLM pipeline
│   ├── reasoning_agent.py      # LLM summarisation & fact extraction
│   └── search_results_agent.py # SERP link categorisation
│
└── utils/
    ├── url_handler.py          # Direct-URL extraction shortcut
    ├── helpers.py              # Pure utility functions
    └── exceptions.py           # Custom exception hierarchy
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY
```

### 3. Run

```bash
# Natural-language query
python start.py --query "tell me about Sundar Pichai"

# Direct URL
python start.py --query "https://en.wikipedia.org/wiki/Black_hole"

# Headless (no browser window)
python start.py --query "latest AI research papers" --headless

# Limit internal steps
python start.py --query "explain quantum computing" --steps 15
```

---

## How It Works

```
start.py
  ├─ is_direct_url?
  │     YES → URLHandler → BrowserTool → ContentExtractionAgent → Summary
  │
  └─ NO  → MainAgent
               ├─ _extract_search_term()          Strip filler phrases
               ├─ _navigate_to_search_engine()    Try Google → DDG → Bing
               │     └─ CaptchaAgent              Detect CAPTCHA → fallback
               ├─ _analyse_search_page()          Categorise SERP links
               │     └─ SearchResultsAgent
               ├─ ReasoningAgent.pick_best_url()  LLM URL ranking
               ├─ click best result               Navigate to target page
               └─ ContentExtractionAgent          DOM strip + LLM summary
                     ├─ DOMAgent                  BeautifulSoup cleaning
                     └─ ReasoningAgent            Gemini summarisation
```

---

## Key Design Decisions

| Feature | Implementation |
|---|---|
| Anti-bot stealth | `navigator.webdriver = undefined`, realistic UA, no automation flags |
| CAPTCHA handling | Detect → signal → fall back to next search engine |
| Popup removal | JS injection + button-click heuristics |
| Search fallback | Google → DuckDuckGo → Bing (configurable in `agent_config.py`) |
| LLM degradation | If `GOOGLE_API_KEY` missing, returns raw text preview instead |
| Structured payloads | All inter-agent communication via `ActionResponse` |

---

## Configuration

All constants live in `config/agent_config.py`:

- `SEARCH_ENGINES` — add/remove/reorder search engines
- `MAX_SEARCH_RESULTS_TO_TRY` — how many SERP links to attempt
- `BROWSER_TIMEOUT_MS` — Playwright navigation timeout
- `LLM_MODEL` — Gemini model name
- `NOISE_TAGS` — HTML tags stripped before text extraction
