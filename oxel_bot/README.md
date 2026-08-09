# 🪵 Oxel Bot — Production Telegram E-Commerce Platform

**Tools for the Digital Craft**

A fully production-ready, end-to-end e-commerce ecosystem built for **Oxel** — a premium wooden desk accessory brand based in Ethiopia. Features a Telegram bot customer storefront, multi-item persistent cart, atomic inventory control, dedicated payment verification state machine, referral/loyalty ledgers, Alembic database migrations, a secure Web Admin Portal, PDF invoice & shipping label generation, and a comprehensive automated test suite.

---

## 🏗️ System Architecture

```
                       ┌─────────────────────────┐
                       │  Telegram Bot Interface │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Handlers Layer         │
                       │  start · catalog · cart │
                       │  checkout · payment     │
                       │  tracking · admin       │
                       │  loyalty · bundle       │
                       └────────────┬────────────┘
                                    │
    ┌───────────────────────────────┴────────────────────────────┐
    │                                                            │
    ▼                                                            ▼
┌──────────────────────────────┐          ┌──────────────────────────────────┐
│  Web Admin Portal (Flask)    │          │  Business Services Layer         │
│  • Secure Password Login     │          │  • cart_service                  │
│  • Session-based Auth        │          │  • order_service                 │
│  • Payment Verify/Reject     │ ────────►│  • payment_service               │
│  • Variant Stock Management  │          │  • inventory_service             │
│  • Shipping Label Generator  │          │  • referral_service              │
│  • Audit Log Viewer          │          │  • loyalty_service               │
└──────────────────────────────┘          │  • promo_service                 │
                                          │  • admin_service                 │
                                          └────────────────┬─────────────────┘
                                                           │
                                                           ▼
                                          ┌──────────────────────────────────┐
                                          │  SQLAlchemy ORM + Alembic        │
                                          │  SQLite (dev) / PostgreSQL (prod)│
                                          └──────────────────────────────────┘
```

---

## 🌟 Feature Set

### 1. Multi-Item Order Architecture
- DB-backed `Order` → `OrderItem` relationship with **frozen unit prices** at checkout
- Multi-item cart converts cleanly to a structured order with full line-item history
- Legacy `order.product_id` / `order.quantity` kept for backward compatibility

### 2. Persistent Cart
- DB-backed `Cart` and `CartItem` — survives bot & server restarts
- Multiple products, multiple variants, customization notes per item
- Stale out-of-stock cart items are detected at checkout

### 3. Atomic Inventory System
- Row-level lock-protected stock deductions via `SELECT...FOR UPDATE`
- Prevents negative balances and overselling under concurrent load
- Auto-rollback if any cart item fails to deduct during checkout
- Inventory restored automatically on payment rejection or order cancellation

### 4. Delivery Code Confirmation
- 6-digit numeric delivery code generated at order creation
- `/ship ORDER#` sends code to customer; `/confirm_delivery ORDER# CODE` validates and marks `delivered`
- Wrong code = hard denial; correct code = stock-proof delivery fulfillment
- Loyalty points auto-awarded on confirmed delivery

### 5. Referral & Loyalty Ledger
- Full `LoyaltyTransaction` audit trail — every change is recorded
- Self-referral and duplicate referral prevention
- Negative balance prevention on point redemptions
- VIP tier auto-promotion: Bronze → Silver (1 000 pts) → Gold (2 000 pts)
- Referral bonus: +500 pts to referrer on first order of referred user

### 6. Promo Code System
- Server-side validation (prevents client-side manipulation)
- Supports: % discount, fixed ETB discount, expiry date, max uses, per-user limit, minimum order value
- Duplicate and expired code prevention
- Special `MYPOINTS` / loyalty redemption code via cart

### 7. Database Migrations (Alembic)
- Full Alembic configuration with `alembic.ini` and `env.py`
- SQLite for local development, PostgreSQL for production (configurable via `DATABASE_URL`)
- Migration scripts: initial full schema + incremental `delivery_code` addition

### 8. Security
- **Admin authentication**: Session-based password login in Web Admin (`ADMIN_PASSWORD` env var)
- **Admin authorization**: Telegram admin commands gated by `ADMIN_IDS` whitelist
- **No secrets committed**: `.env` excluded from git; only `.env.example` committed
- **Input validation**: Promo codes, quantities, prices all validated server-side
- **Audit logging**: `AdminAuditLog` table tracks payment verification, stock changes, loyalty adjustments
- **CSRF mitigation**: Flask `secret_key` set from env; session cookies are HTTP-only

### 9. Error Handling & Logging
- `logging` module with structured handlers throughout all services
- Specific `logger.warning()` / `logger.exception()` on all failure paths
- No silent `except: pass` on critical business logic paths
- Telegram notification failures log warnings but don't crash order processing

### 10. Persistent Cart (Bot-Restart Safe)
- Cart stored in database, not Telegram `context.user_data`
- Cart state persists across bot restarts, crashes, and Telegram server interruptions

### 11. Dynamic Product Variants (CMS)
- Admin CMS allows per-variant stock management via inline buttons
- `/setstock PROD_ID FINISH QTY` command for rapid CLI-style stock updates
- `+5 quick-add` and `Set Exact Qty` inline buttons per variant in the product editor

### 12. Automated Test Suite — 15 Tests
```
tests/
├── test_cart.py              # Cart add/remove/quantity, persistence
├── test_orders.py            # Multi-item checkout, promo discounts, stock deduction
├── test_payments.py          # Payment lifecycle, duplicate reference prevention
├── test_inventory.py         # Atomic deduction, negative stock prevention
├── test_delivery_confirmation.py  # Code generation, validation, loyalty award
├── test_referrals_loyalty.py # Self-referral, duplicate, negative balance prevention
└── test_security.py          # Web Admin auth redirect, login validation
```

### 13. Admin Architecture
- **Telegram Admin**: Quick actions — verify orders, ship, bulk dispatch, give loyalty points, broadcast, CRM
- **Web Admin Portal**: Tabular order management, inventory control, audit trail viewer, shipping labels
- **Shared service layer**: Both admin interfaces call the same business logic (no duplication)

### 14. Bundle Wizard
- Step-by-step multi-item bundle configurator (Creator Bundle, Studio Bundle)
- Color/finish selection per bundle component with navigation (Back / Forward)
- Bundle items resolved at runtime from `BUNDLE_ITEMS` config — no migration needed

### 15. PDF Invoice & Shipping Label Generation
- Auto-generated PDF invoice sent to customer on payment verification
- Shipping label PDF (with delivery code) sent to admin on `/ship`
- Both generated using `reportlab`

---

## 🚀 Quick Start

### Prerequisites

```bash
git clone <repo-url>
cd oxel_bot
pip install -r requirements.txt
```

### Environment Configuration

Copy `.env.example` to `.env` and populate:

```bash
cp .env.example .env
```

Required environment variables:

| Variable          | Description                                         |
|-------------------|-----------------------------------------------------|
| `BOT_TOKEN`       | Telegram Bot Token from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL`    | `sqlite:///oxel_bot.db` (dev) or `postgresql://...` (prod) |
| `ADMIN_USER_IDS`  | Comma-separated Telegram User IDs for bot admins    |
| `ADMIN_PASSWORD`  | Web Admin Portal password                           |
| `FLASK_SECRET_KEY`| Flask session secret (generate a strong random key) |

### Database Setup

```bash
# Run Alembic migrations to initialize all tables
python -m alembic upgrade head

# Seed products, variants, and promo codes
python database.py
```

### Run Tests

```bash
python -m unittest discover tests
```

Expected result: `Ran 15 tests in ~2s — OK`

### Start the Application

**Telegram Bot:**
```bash
python bot.py
```

**Web Admin Portal** (separate terminal):
```bash
python web_admin.py
```

Access the admin portal at: `http://localhost:5000`

---

## 🐳 Docker Deployment

```bash
# Build image
docker build -t oxel-ecommerce-bot .

# Run with environment file
docker run -d \
  --name oxel-bot-app \
  -p 5000:5000 \
  --env-file .env \
  oxel-ecommerce-bot
```

---

## 🗄️ Database Models

| Model                | Purpose                                              |
|----------------------|------------------------------------------------------|
| `User`               | Customer profile, VIP tier, loyalty balance          |
| `Product`            | Product catalog with slug and category               |
| `ProductVariant`     | Finish variants with individual stock quantities     |
| `Cart` / `CartItem`  | Persistent multi-item shopping cart                  |
| `Order`              | Multi-item order with frozen prices and delivery code|
| `OrderItem`          | Line items with frozen unit prices                   |
| `Payment`            | Payment lifecycle state machine                      |
| `OrderStatusHistory` | Immutable status change audit log                    |
| `Referral`           | Referral link with reward tracking                   |
| `LoyaltyTransaction` | Complete points ledger (positive & negative)         |
| `PromoCode`          | Promo code with usage limits and expiry              |
| `AdminAuditLog`      | Admin action audit trail                             |

---

## 🛡️ Security Notes

- **Never commit `.env`** — all secrets via environment variables
- **Rotate Bot Token** if ever exposed (via @BotFather)
- **PostgreSQL Production**: Use SSL (`?sslmode=require` in `DATABASE_URL`)
- **Flask Secret Key**: Use a cryptographically random value (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)

### Database Backup (PostgreSQL Production)
```bash
pg_dump -U postgres -d oxel_db > backup_$(date +%Y%m%d).sql
```

---

## 📋 Admin Commands Reference

| Command                              | Description                                 |
|--------------------------------------|---------------------------------------------|
| `/admin`                             | Open admin panel                            |
| `/verify ORDER#`                     | Verify payment & generate PDF invoice       |
| `/status ORDER# STATUS`              | Update order status                         |
| `/ship ORDER# [TRACKING]`            | Mark shipped & send delivery code           |
| `/bulkship OXEL-1,OXEL-2`           | Bulk mark as shipped                        |
| `/confirm_delivery ORDER# CODE`      | Confirm delivery with customer code         |
| `/shipping_label ORDER#`             | Generate & send shipping label PDF          |
| `/setstock PROD_ID FINISH QTY`       | Set variant stock quantity                  |
| `/givepoints USER_ID POINTS [reason]`| Award loyalty points (with audit log)       |
| `/userinfo USER_ID`                  | View customer profile                       |
| `/broadcast MSG`                     | Send message to all users                   |
| `/broadcast_vip MSG`                 | Send to Gold/Silver VIP users only          |
| `/addproduct Name \| Cat \| Price \| Desc` | Add new product                       |
| `/addpromo CODE PERCENT`             | Create promo code                           |

---

## 📄 License

Proprietary — Oxel E-Commerce © 2026
