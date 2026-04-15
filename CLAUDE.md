# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Gmail daily summary system that fetches recent emails via Gmail API, summarizes them with Gemini AI, and sends the result to Telegram. Runs in two modes: a local Flask web app with a scheduler, or a headless GitHub Actions job.

## Setup & Running

```bash
# Install dependencies
pip install -r requirements.txt
pip install google-genai   # not yet in requirements.txt but required by email_summarizer.py

# Run the web dashboard (http://localhost:5000)
python app.py

# Run headless (used by GitHub Actions)
python run_summary.py
```

The first time Gmail auth runs, a browser window opens for OAuth consent. The resulting `token.json` is auto-saved and reused on subsequent runs.

## Architecture

### Two Execution Modes

**Local web app (`app.py`)**
- Flask server on port 5000 with a single-page dashboard (`templates/dashboard.html`)
- APScheduler fires `scheduled_job()` daily at 09:00 KST
- `POST /api/run` triggers a manual run; result is appended to `history.json` (capped at 30 entries)
- Config (API keys) is read/written through `GET|POST /api/config` → stored in `config.json`

**GitHub Actions (`run_summary.py` + `.github/workflows/daily_summary.yml`)**
- Runs at UTC 00:00 (= KST 09:00) via cron, or on `workflow_dispatch`
- Reads `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` from repository secrets
- Restores `token.json` and `credentials.json` from base64-encoded secrets (`GMAIL_TOKEN`, `GMAIL_CREDENTIALS`)
- Writes env vars into `config.json` then calls `run_daily_summary()` identically to the web app

### Core Logic (`email_summarizer.py`)

`run_daily_summary()` is the single entry point for both modes:
1. `get_gmail_service()` — OAuth2 auth, refreshing `token.json` automatically
2. `fetch_recent_emails(service, hours=24)` — queries Gmail API for messages in the last 24 h (max 50); `parse_email()` extracts headers + body (truncated at 2000 chars)
3. `summarize_with_gemini(emails, api_key)` — sends a formatted prompt to `gemini-2.0-flash` via `google-genai`
4. `send_telegram(token, chat_id, message)` — optional Telegram delivery

Config priority: `config.json` values are used first; environment variables fill in missing keys (see `run_daily_summary()` lines 203–212).

### Known Inconsistency: Anthropic vs. Gemini

`requirements.txt` declares `anthropic>=0.40.0` and the dashboard UI labels the key field as "Anthropic API Key", but **the actual summarization code uses `google-genai` (Gemini)**, not the Anthropic SDK. The config key the code reads is `gemini_api_key`, not `anthropic_api_key`. `google-genai` is also absent from `requirements.txt` and is installed separately in the CI workflow. If switching the summarizer to Claude, update `summarize_with_gemini()`, the config key name, and `requirements.txt`.

## Key Files (gitignored — must be supplied manually or via secrets)

| File | Purpose |
|---|---|
| `credentials.json` | Google OAuth client secret (download from Cloud Console) |
| `token.json` | OAuth access/refresh token (auto-generated after first login) |
| `config.json` | Runtime config: `gemini_api_key`, `telegram_bot_token`, `telegram_chat_id` |

## GitHub Actions Secrets Required

`GMAIL_TOKEN`, `GMAIL_CREDENTIALS` (base64-encoded files), `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
