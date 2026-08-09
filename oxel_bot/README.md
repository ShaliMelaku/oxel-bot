# 🪵 Oxel Bot — Production Telegram E-Commerce Platform

**Tools for the Digital Craft**

A fully production-ready, end-to-end e-commerce platform built for **Oxel** — a premium Ethiopian wooden desk accessory brand. Built on Python and `python-telegram-bot`, featuring a native customer storefront, persistent multi-item shopping cart, atomic inventory reservation, automated payment verification workflows, referral/loyalty transaction ledgers, promo code validation engine, and automated PDF invoice & shipping label generation.

---

## 🏗️ System Architecture

```
                       ┌─────────────────────────┐
                       │  Telegram User Interface │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Telegram Bot Core      │
                       │  (python-telegram-bot)  │
                       └────────────┬────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │                    Handlers Layer                       │
       │  start · catalog · cart · checkout · payment            │
       │  tracking · admin · loyalty · bundle · profile · reviews │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │                Business Services Layer                  │
       │  • cart_service      • order_service     • payment_service  │
       │  • inventory_service • referral_service  • loyalty_service  │
       │  • promo_service     • admin_service                      │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │               SQLAlchemy ORM Data Access                │
       │          SQLite (dev/WAL) / PostgreSQL (prod)           │
       └─────────────────────────────────────────────────────────┘
```

---

## 🌟 Key Features

### 🛒 1. Persistent Multi-Item Cart
- Database-backed `Cart` and `CartItem` state that survives bot and server restarts.
- Supports multiple product variants (wood finishes, sizes) and custom engraving notes per item.
- Real-time cart stock checking prevents checkout of out-of-stock items.

### 🔒 2. Atomic Inventory Management
- Concurrency-safe stock deduction using database row locks (`SELECT...FOR UPDATE`).
- Prevents negative inventory and overselling under concurrent user checkout spikes.
- Auto-restores stock if payment is rejected or an order is cancelled.

### 📦 3. Multi-Item Order Lifecycle & Price Freezing
- Orders freeze product unit prices at checkout time, insulating existing orders from future price modifications.
- Complete line-item audit trail with structured `OrderItem` relations.

### 🔑 4. Secure Delivery Code Verification
- Cryptographically random 6-digit delivery confirmation code (`secrets.randbelow`) assigned per order.
- `/confirm_delivery ORDER# CODE` command allows delivery staff to verify hand-off with the customer.
- Automated loyalty points distribution upon successful delivery confirmation.

### 🏅 5. Loyalty & Referral Engine
- Immutable `LoyaltyTransaction` audit ledger tracking points earned and redeemed.
- Referral system (+100 points for referrer on first order, 5% welcome discount for referred customer).
- VIP tier progression system: **Bronze 🥉** → **Silver 🥈** → **Gold 🥇**.

### 🎟️ 6. Server-Side Promo Engine
- Validates promo codes server-side against discount percentages, fixed ETB values, expiry dates, global usage caps, minimum order values, and per-user usage limits.

### 📄 7. PDF Invoice & Shipping Label Generator
- Auto-generates branded PDF invoices for customers upon payment verification.
- Auto-generates dispatch shipping labels (with delivery verification codes) for fulfillment staff.

---

## 🚀 Quick Start

### 1. Prerequisites & Installation

Ensure Python 3.10+ is installed on your system.

```bash
git clone https://github.com/ShaliMelaku/oxel-bot.git
cd oxel-bot
pip install -r requirements.txt
```

### 2. Environment Setup

Copy `.env.example` to `.env` and enter your Telegram Bot Token and Admin User ID:

```bash
cp .env.example .env
```

Edit `.env`:
```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
ADMIN_USER_IDS=123456789
DATABASE_URL=sqlite:///oxel_bot.db
```

### 3. Initialize & Seed Database

Initialize database tables, variant inventory stock, and promo codes:

```bash
python database.py
```

### 4. Run the Telegram Bot

```bash
python bot.py
```

---

## 🗄️ Database Schema Overview

| Table | Purpose |
| ----- | ------- |
| `users` | Customer profile, VIP tier, loyalty point ledger balance |
| `products` | Product catalog with base pricing and details |
| `product_variants` | Wood finishes, size options, stock levels, and price modifiers |
| `carts` / `cart_items` | Database-backed persistent customer shopping cart |
| `orders` / `order_items` | Multi-item orders with frozen unit pricing and delivery codes |
| `payments` | Payment submission lifecycle & verification state |
| `order_status_history` | Audit log of status transitions per order |
| `referrals` | Referral relationship ledger |
| `loyalty_transactions` | Complete points credit/debit audit trail |
| `promo_codes` | Promotional codes with rule validation parameters |
| `admin_audit_logs` | Admin action audit log |

---

## 📋 Admin Commands

Admin commands are available to Telegram user IDs configured in `ADMIN_USER_IDS`:

| Command | Description |
| ------- | ----------- |
| `/admin` | Open interactive Telegram admin portal |
| `/verify ORDER#` | Verify customer payment & issue PDF invoice |
| `/status ORDER# STATUS` | Update order status (`confirmed`, `shipped`, `delivered`, `cancelled`) |
| `/ship ORDER# [TRACKING]` | Mark order shipped and send delivery code to customer |
| `/confirm_delivery ORDER# CODE` | Fulfill delivery using customer confirmation code |
| `/shipping_label ORDER#` | Generate printable PDF shipping label |
| `/setstock PROD_ID FINISH QTY` | Update variant stock inventory level |
| `/givepoints USER_ID POINTS [reason]` | Award loyalty points to a user |
| `/userinfo USER_ID` | View detailed customer profile & metrics |
| `/broadcast MSG` | Broadcast announcement message to all users |
| `/broadcast_vip MSG` | Broadcast announcement to VIP users (Silver/Gold) |
| `/addpromo CODE PERCENT` | Create a new promotional discount code |

---

## 🛡️ Security & Privacy

- **Secret Isolation**: No bot tokens or database URIs are committed to version control.
- **Fail-Fast Startup**: Bot validates environment variables on boot and halts if secrets are missing.
- **Strict Authorization**: Admin actions gated by Telegram User ID whitelist check.
- **Concurrency Protection**: SQLite WAL mode and SQL row locking prevent database contention and stock race conditions.

---

## 📄 License

Proprietary — Oxel E-Commerce Platform © 2026
