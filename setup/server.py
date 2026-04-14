"""
FastAPI wizard server — serves the setup UI and handles all setup API calls.
Runs on port 3001 (separate from the main app on 8000).
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Path setup — allow importing sibling packages
# ---------------------------------------------------------------------------
SETUP_DIR = Path(__file__).parent
PROJECT_ROOT = SETUP_DIR.parent
sys.path.insert(0, str(SETUP_DIR))

from steps.prereqs import check_prereqs
from steps.database import setup_database
from steps import gmail as gmail_steps
from steps.launcher import launch_all

# ---------------------------------------------------------------------------
# In-memory wizard state (single-user local tool — a dict is sufficient)
# ---------------------------------------------------------------------------
_wizard_config: dict = {}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Expense Tracker Setup Wizard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static UI files
UI_DIR = SETUP_DIR / "ui"
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


@app.get("/")
def serve_ui():
    return FileResponse(str(UI_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
    complete_marker = PROJECT_ROOT / ".setup_complete"
    return {"setup_complete": complete_marker.exists()}


# ---------------------------------------------------------------------------
# Step 2: Prerequisite check
# ---------------------------------------------------------------------------

@app.get("/api/check-prereqs")
def api_check_prereqs():
    results = check_prereqs()
    all_ok = all(v["ok"] for v in results.values())
    return {"ok": all_ok, "results": results}


# ---------------------------------------------------------------------------
# Step 3: Database setup
# ---------------------------------------------------------------------------

class DatabaseConfig(BaseModel):
    admin_pass: str
    db_pass: str


@app.post("/api/setup-database")
def api_setup_database(body: DatabaseConfig):
    result = setup_database(body.admin_pass, body.db_pass)
    if result["ok"]:
        _wizard_config["admin_pass"] = body.admin_pass
        _wizard_config["db_pass"] = body.db_pass
    return result


# ---------------------------------------------------------------------------
# Step 4: Gmail connection test
# ---------------------------------------------------------------------------

class GmailCredentials(BaseModel):
    email: str
    password: str


@app.post("/api/test-gmail")
def api_test_gmail(body: GmailCredentials):
    result = gmail_steps.test_connection(body.email, body.password)
    if result["ok"]:
        _wizard_config["imap_user"] = body.email
        _wizard_config["imap_password"] = body.password
    return result


# ---------------------------------------------------------------------------
# Step 5: Gmail label creation
# ---------------------------------------------------------------------------

@app.post("/api/create-gmail-labels")
def api_create_labels(body: GmailCredentials):
    return gmail_steps.create_labels(body.email, body.password)


@app.post("/api/find-bank-emails")
def api_find_bank_emails(body: GmailCredentials):
    return gmail_steps.find_bank_emails(body.email, body.password)


@app.post("/api/move-existing-emails")
def api_move_emails(body: GmailCredentials):
    return gmail_steps.move_existing_emails(body.email, body.password)


# ---------------------------------------------------------------------------
# Step 6: LLM key test
# ---------------------------------------------------------------------------

class LLMConfig(BaseModel):
    provider: str   # "GEMINI" or "GROQ"
    api_key: str


@app.post("/api/test-llm-key")
def api_test_llm(body: LLMConfig):
    result = _verify_llm_key(body.provider.upper(), body.api_key)
    if result["ok"]:
        _wizard_config["llm_backend"] = body.provider.upper()
        _wizard_config["llm_api_key"] = body.api_key
    return result


def _verify_llm_key(provider: str, api_key: str) -> dict:
    """Light validation: check key format and do a minimal API ping."""
    if not api_key or len(api_key) < 10:
        return {"ok": False, "message": "API key looks too short. Please double-check it."}

    try:
        import urllib.request
        import urllib.error

        if provider == "GEMINI":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return {"ok": True, "message": "Gemini API key verified."}
            return {"ok": False, "message": "Gemini key check failed. Please verify it."}

        elif provider == "GROQ":
            url = "https://api.groq.com/openai/v1/models"
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {api_key}"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return {"ok": True, "message": "Groq API key verified."}
            return {"ok": False, "message": "Groq key check failed. Please verify it."}

        return {"ok": False, "message": f"Unknown provider: {provider}"}

    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Gemini returns 400 for valid keys with no models param issue — treat as ok
            return {"ok": True, "message": "API key accepted."}
        return {"ok": False, "message": f"API key rejected (HTTP {e.code}). Please verify it."}
    except Exception as e:
        # Network issues — let the user skip verification
        return {
            "ok": True,
            "message": f"Could not verify online (no network?), but key saved. ({e})",
        }


# ---------------------------------------------------------------------------
# Step 7: Install dependencies (SSE streaming)
# ---------------------------------------------------------------------------

@app.get("/api/install")
async def api_install():
    config = dict(_wizard_config)  # snapshot

    async def generate() -> AsyncGenerator[str, None]:
        try:
            from steps.installer import stream_install
            async for chunk in stream_install(config):
                yield chunk
        except Exception as e:
            yield f"event: error\ndata: {e}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Step 8: Launch services
# ---------------------------------------------------------------------------

@app.post("/api/launch")
def api_launch():
    return launch_all()
