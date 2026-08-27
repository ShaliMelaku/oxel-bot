import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _require_env(key: str, description: str) -> str:
    """Fail fast if a required environment variable is missing or is a placeholder."""
    value = os.getenv(key, '').strip()
    placeholders = {
        'YOUR_TELEGRAM_BOT_TOKEN_HERE',
        'generate-a-strong-random-key-here',
        'generate_random_secret_key_here',
        '',
    }
    if not value or value in placeholders:
        print(f"\n[FATAL] Missing or placeholder environment variable: {key}")
        print(f"        {description}")
        print(f"        Set it in your .env file. See .env.example for reference.\n")
        sys.exit(1)
    return value


def _require_int_env(key: str, description: str) -> int:
    """Fail fast if a required integer env var is missing or unparseable."""
    value = os.getenv(key, '').strip()
    if not value:
        print(f"\n[FATAL] Missing environment variable: {key}")
        print(f"        {description}")
        print(f"        Set it in your .env file. See .env.example for reference.\n")
        sys.exit(1)
    try:
        return int(value)
    except ValueError:
        print(f"\n[FATAL] Invalid value for {key}: '{value}' (expected integer)")
        sys.exit(1)


# ── Required secrets (no fallback — will crash at startup if missing) ──────────
BOT_TOKEN = _require_env('BOT_TOKEN', 'Telegram bot token from @BotFather.')
FLASK_SECRET_KEY = _require_env(
    'FLASK_SECRET_KEY',
    'Strong random key for Flask session encryption. Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
)
ADMIN_PASSWORD = _require_env(
    'ADMIN_PASSWORD',
    'Password for the web admin dashboard. Use a strong, unique password.'
)

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///oxel_bot.db')

# ── Admin IDs ─────────────────────────────────────────────────────────────────
_admin_ids_raw = os.getenv('ADMIN_USER_IDS', '').strip()
ADMIN_IDS = [int(i.strip()) for i in _admin_ids_raw.split(',') if i.strip().isdigit()]
if not ADMIN_IDS:
    print("[WARNING] ADMIN_USER_IDS is empty — no Telegram admins configured.")

# ── Bot & Shop Info ────────────────────────────────────────────────────────────
BOT_USERNAME = os.getenv('BOT_USERNAME', 'oxeletbot')
SHOP_NAME = os.getenv('SHOP_NAME', 'Oxel')
SHOP_WEBSITE = os.getenv('SHOP_WEBSITE', 'https://oxel.com')
TELEBIRR_NUMBER = os.getenv('TELEBIRR_NUMBER', '')
CBE_NUMBER = os.getenv('CBE_NUMBER', '')
TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL', '')
INSTAGRAM_URL = os.getenv('INSTAGRAM_URL', '')
TIKTOK_URL = os.getenv('TIKTOK_URL', '')

# ── Web Admin Rate Limiting ────────────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
LOGIN_LOCKOUT_SECONDS = int(os.getenv('LOGIN_LOCKOUT_SECONDS', '900'))  # 15 minutes
