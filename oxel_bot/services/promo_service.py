import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import PromoCode, Order, User

logger = logging.getLogger(__name__)

# Loyalty tier rank — higher number = higher tier
TIER_RANK = {
    "Bronze 🥉": 1,
    "Silver 🥈": 2,
    "Gold 🥇": 3,
}


def validate_promo_code(db: Session, code_str: str, user_id: int, cart_subtotal: int,
                        cart_product_ids: list = None) -> dict:
    """
    Validate promo code server-side. Checks:
    - Active status + expiration
    - Global usage cap (max_uses set by admin; NULL = unlimited)
    - Per-user usage limit (default 1 — single use per person)
    - Minimum order value
    - Product restrictions (allowed_product_ids — cart must contain an eligible product)
    - Loyalty tier restrictions (min_loyalty_tier — user must meet minimum tier)

    Returns dict: {'valid': bool, 'discount_amount': int, 'message': str, 'promo': PromoCode}
    """
    if not code_str:
        return {'valid': False, 'discount_amount': 0, 'message': "No code provided", 'promo': None}

    promo = db.query(PromoCode).filter(PromoCode.code == code_str.strip().upper()).first()
    if not promo or not promo.active:
        return {'valid': False, 'discount_amount': 0, 'message': "Invalid or inactive promo code.", 'promo': None}

    now = datetime.now()

    # ── Expiration ────────────────────────────────────────────────────────────
    if promo.start_date and now < promo.start_date:
        return {'valid': False, 'discount_amount': 0, 'message': "Promo code is not active yet.", 'promo': None}
    if promo.expiration_date and now > promo.expiration_date:
        promo.active = False
        db.commit()
        return {'valid': False, 'discount_amount': 0, 'message': "Promo code has expired.", 'promo': None}

    # ── Global usage cap (admin-set, NULL = unlimited) ─────────────────────────
    if promo.max_uses is not None and promo.max_uses > 0:
        if (promo.current_uses or 0) >= promo.max_uses:
            promo.active = False
            db.commit()
            return {'valid': False, 'discount_amount': 0,
                    'message': "This promo code has reached its usage limit.", 'promo': None}

    # ── Minimum order value ───────────────────────────────────────────────────
    if promo.min_order_value and cart_subtotal < promo.min_order_value:
        return {'valid': False, 'discount_amount': 0,
                'message': f"Minimum order value of {promo.min_order_value:,} ETB required.", 'promo': None}

    # ── Per-user limit (default 1 = single-use per person) ───────────────────
    per_user = promo.per_user_limit if (promo.per_user_limit is not None and promo.per_user_limit > 0) else 1
    user_uses = db.query(Order).filter(
        Order.user_id == user_id,
        Order.promo_code == promo.code
    ).count()
    if user_uses >= per_user:
        return {'valid': False, 'discount_amount': 0,
                'message': "You have already used this promo code.", 'promo': None}

    # ── Product restriction ───────────────────────────────────────────────────
    if promo.allowed_product_ids and promo.allowed_product_ids.strip():
        allowed_ids = {int(p.strip()) for p in promo.allowed_product_ids.split(',') if p.strip().isdigit()}
        if allowed_ids:
            cart_ids = set(cart_product_ids or [])
            if not cart_ids.intersection(allowed_ids):
                from database import Product
                prod_names = [p.name for p in db.query(Product).filter(Product.id.in_(allowed_ids)).all()]
                return {'valid': False, 'discount_amount': 0,
                        'message': f"This promo only applies to: {', '.join(prod_names) or 'specific products'}.",
                        'promo': None}

    # ── Loyalty tier restriction ──────────────────────────────────────────────
    if promo.min_loyalty_tier and promo.min_loyalty_tier.strip():
        user = db.query(User).filter(User.user_id == user_id).first()
        user_tier = (user.vip_tier if user and user.vip_tier else "Bronze 🥉")
        if TIER_RANK.get(user_tier, 1) < TIER_RANK.get(promo.min_loyalty_tier, 1):
            return {'valid': False, 'discount_amount': 0,
                    'message': f"This promo requires {promo.min_loyalty_tier} loyalty status or higher.",
                    'promo': None}

    # ── Calculate discount ────────────────────────────────────────────────────
    discount = 0
    if promo.discount_percent and promo.discount_percent > 0:
        discount = int(cart_subtotal * (promo.discount_percent / 100.0))
    elif promo.discount_amount and promo.discount_amount > 0:
        discount = promo.discount_amount
    discount = min(discount, cart_subtotal)

    return {
        'valid': True,
        'discount_amount': discount,
        'message': f"✅ Promo applied! You save {discount:,} ETB",
        'promo': promo
    }


def record_promo_usage(db: Session, code_str: str):
    """
    Increment usage counter. Auto-deactivates only when admin-set max_uses is reached.
    NULL max_uses = unlimited globally; per_user_limit handles per-person enforcement.
    """
    if not code_str:
        return
    promo = db.query(PromoCode).filter(PromoCode.code == code_str.strip().upper()).first()
    if promo:
        promo.current_uses = (promo.current_uses or 0) + 1
        if promo.max_uses is not None and promo.max_uses > 0:
            if promo.current_uses >= promo.max_uses:
                promo.active = False
                logger.info(f"Promo '{promo.code}' auto-deactivated after {promo.current_uses}/{promo.max_uses} uses.")
        db.commit()
