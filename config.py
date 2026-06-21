import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_data.db")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    
    # Max conversation history length per user (both user and bot messages combined)
    MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "10"))

    # Parse admin user IDs from a comma-separated string
    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = []
    if raw_admin_ids:
        try:
            ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip()]
        except ValueError:
            print("WARNING: ADMIN_IDS environment variable contains non-integer values. Please check your configuration.")

    @classmethod
    def validate(cls):
        """Validate critical configuration variables."""
        errors = []
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is missing or empty.")
        if not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is missing or empty.")
        if not cls.ADMIN_IDS:
            errors.append("ADMIN_IDS is missing or empty. At least one Admin Telegram ID is required for administrative commands.")
        return errors
