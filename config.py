"""Configuration S1 — chemins locaux + LLM commutable (gratuit -> Claude)."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
DB_PATH     = DATA_DIR / "actuelia.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
UPLOADS_DIR = DATA_DIR / "uploads"
CV_DIR      = DATA_DIR / "cv"

# --- LLM : "openai_compat" (gratuit, pour tester) | "anthropic" (après validation) ---
LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "openai_compat")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# Fournisseur OpenAI-compatible (gratuit : Gemini, Groq, Mistral, OpenRouter…)
LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
LLM_MODEL    = os.getenv("LLM_MODEL", "gemini-2.5-flash")

# Anthropic (plus tard)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def llm_configure() -> bool:
    return bool(ANTHROPIC_API_KEY) if LLM_PROVIDER == "anthropic" else bool(LLM_API_KEY)


for _d in (DATA_DIR, UPLOADS_DIR, CV_DIR):
    _d.mkdir(parents=True, exist_ok=True)
