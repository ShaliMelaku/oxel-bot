# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| Latest  | ✅ Yes    |

---

## Reporting a Vulnerability

If you discover a security vulnerability in this project, **please do NOT open a public GitHub issue**.

Instead, report it privately to the repository maintainers via Telegram. We aim to respond to security reports within 48 hours.

---

## Security Requirements for Deployment

Before running the bot in production, you **MUST** configure the following in your `.env` file:

| Variable | Requirement |
| -------- | ----------- |
| `BOT_TOKEN` | Secret Telegram Bot Token issued by @BotFather |
| `ADMIN_USER_IDS` | Comma-separated list of numeric Telegram User IDs authorized for admin commands |
| `DATABASE_URL` | Database connection URI (`sqlite:///...` or `postgresql://...`) |

---

## Technical Security Mitigations

| Vulnerability Threat | Mitigation Implementation |
| ------------------- | ------------------------- |
| **Secret Exposure** | Zero hardcoded tokens or sensitive keys in source code. Bot fails fast at startup if `.env` or required keys are missing. |
| **Unauthorized Admin Access** | Telegram admin commands and callback queries strictly gated against `ADMIN_USER_IDS` whitelist. |
| **SQL Injection** | Built on SQLAlchemy ORM using parameterized queries. No raw string interpolation in database operations. |
| **Inventory Race Conditions** | Row-level locking via `with_for_update()` during stock deduction prevents double-allocation under concurrent checkouts. |
| **Input Overflow & Spoofing** | Server-side validation and truncation on prices, promo codes, custom engraving inputs, and contact phone numbers. |
| **Delivery Verification Guessing** | Cryptographically secure 6-digit delivery confirmation codes generated via Python `secrets.randbelow()`. |
| **Database Lock Contention** | SQLite connection configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL`), `PRAGMA foreign_keys=ON`, and busy timeout handling. |
| **Promo Code Abuse** | Server-side promo engine enforces expiration dates, usage limits, minimum order values, and per-user single-use constraints. |

---

## Protected & Excluded Files

The following files contain local state, customer data, or deployment secrets and must **NEVER** be committed:

```text
.env                  — Contains live bot tokens and secret credentials
*.db / *.sqlite       — Production SQLite database containing customer & order records
*.log                 — System logs
```

All sensitive patterns are pre-configured in `.gitignore`.
