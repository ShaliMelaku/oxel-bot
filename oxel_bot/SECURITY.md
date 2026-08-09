# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| Latest  | ✅ Yes    |

---

## Reporting a Vulnerability

If you discover a security vulnerability in this project, **please do NOT open a public GitHub issue**.

Instead, report it privately:

- **Telegram**: Contact the repository owner directly.
- **Response time**: We aim to respond within 48 hours.

---

## Security Requirements for Deployment

Before running this bot in production, you **MUST** configure the following in your `.env` file:

| Variable | Requirement |
| -------- | ----------- |
| `BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `FLASK_SECRET_KEY` | A cryptographically random 32+ byte hex string |
| `ADMIN_PASSWORD` | A strong, unique password (12+ chars, mixed case, symbols) |
| `ADMIN_USER_IDS` | Your real Telegram user ID(s) |

### Generate a strong Flask secret key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## What We Protect Against

| Threat | Protection |
| ------ | ---------- |
| **Secret exposure** | No hardcoded secrets; bot crashes at startup if `.env` is missing |
| **Brute-force login** | IP-based rate limiting: 5 attempts → 15-minute lockout |
| **CSRF attacks** | Per-session CSRF tokens on all admin POST forms |
| **Clickjacking** | `X-Frame-Options: DENY` header on all responses |
| **XSS** | `Content-Security-Policy` + `X-XSS-Protection` headers |
| **SQL Injection** | SQLAlchemy ORM (parameterized queries, no raw SQL) |
| **Race conditions** | `with_for_update()` row-level locking on stock deductions |
| **Session fixation** | Session regenerated on successful login |
| **Quantity overflow** | Input validation: quantity must be 1–9999 |
| **DB corruption** | SQLite WAL mode + `PRAGMA foreign_keys=ON` |
| **Concurrent load** | Connection pooling + `busy_timeout=5000` |
| **Delivery code guessing** | `secrets.randbelow()` (CSPRNG) for 6-digit codes |

---

## Files That Must NEVER Be Committed

```text
.env                  — Contains your bot token and passwords
*.db / *.sqlite       — Contains customer data
*.log                 — May contain sensitive operational data
scratch/              — Local dev scratch files
data/                 — Local product data (may vary from production)
```

All of these are covered by `.gitignore`.

---

## Database Security Notes

- **SQLite**: WAL journal mode enabled for concurrent access safety.
- **FK integrity**: `PRAGMA foreign_keys=ON` enforced at connection level.
- **Timestamps**: All stored as UTC (`datetime.now(timezone.utc)`) to prevent timezone confusion.
- **Delivery codes**: Generated with `secrets.randbelow()` (cryptographically secure RNG).
