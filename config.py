from dotenv import load_dotenv
import os
import sys
import threading

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PROJECT_ID = os.getenv("PROJECT_ID", "test-shop-1")
MODEL = os.getenv("MODEL", "gpt-5-mini")
TOOL_MODEL = os.getenv(
    "TOOL_MODEL", "gpt-4.1-mini"
)  # deterministic (temperature=0) for tool rounds
ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gpt-4.1-mini")  # same model for final answer

# Model tiers — opaque tier name → concrete (tool, answer) models.
# Single source of truth; change models via env vars, no code/plugin release.
MODEL_TIERS = {
    "fast": {
        "tool": os.getenv("TIER_FAST_TOOL", "gpt-4.1-mini"),
        "answer": os.getenv("TIER_FAST_ANSWER", "gpt-4.1-mini"),
    },
    "powerful": {
        "tool": os.getenv("TIER_POWERFUL_TOOL", "gpt-4.1"),
        "answer": os.getenv("TIER_POWERFUL_ANSWER", "gpt-4.1-mini"),
    },
}
DEFAULT_MODEL_TIER = "fast"


def resolve_tier(tier: str) -> tuple[str, str]:
    """Map a tier name to (tool_model, answer_model); unknown -> default tier."""
    cfg = MODEL_TIERS.get(tier) or MODEL_TIERS[DEFAULT_MODEL_TIER]
    return cfg["tool"], cfg["answer"]


# Thread-local project ID override (for concurrent chat requests)
_local = threading.local()


def get_project_id() -> str:
    """Get the active project ID (thread-local override or global default)."""
    return getattr(_local, "project_id", None) or PROJECT_ID


def set_project_id(pid: str) -> None:
    """Set thread-local project ID override."""
    _local.project_id = pid


def clear_project_id() -> None:
    """Clear thread-local override, revert to global."""
    _local.project_id = None


# Webhook-specific (not required for CLI/chatbot)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
CONTEXT_MODEL = os.getenv("CONTEXT_MODEL", "gpt-4o-mini")

_missing = [
    name
    for name, val in [
        ("OPENAI_API_KEY", OPENAI_API_KEY),
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_KEY", SUPABASE_KEY),
    ]
    if not val
]

PORT = int(os.getenv("PORT", "8000"))

if _missing:
    print(f"ERROR: Missing required environment variables: {', '.join(_missing)}")
    print("Copy .env.example to .env and fill in your credentials.")
    sys.exit(1)
