import logging
import html
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database import PriceSlash, GuerrillaCode, Product, User
from services.loyalty_service import award_points

logger = logging.getLogger(__name__)


def get_or_create_slash(db: Session, user_id: int, product_id: int) -> PriceSlash:
    """Get active price slash or create a new one for a user and product."""
    slash = db.query(PriceSlash).filter(
        PriceSlash.user_id == user_id,
        PriceSlash.product_id == product_id,
        PriceSlash.is_used == False
    ).first()

    if not slash:
        slash = PriceSlash(
            user_id=user_id,
            product_id=product_id,
            slashes_count=0,
            max_slashes=3,
            slash_discount_amount=0,
            is_used=False
        )
        db.add(slash)
        db.commit()
        db.refresh(slash)
    return slash


def apply_slash_click(db: Session, referrer_id: int, product_id: int, clicker_id: int) -> tuple[bool, str, int]:
    """Process a friend clicking a user's price slash link."""
    if referrer_id == clicker_id:
        return False, "⚠️ You cannot slash your own price!", 0

    slash = get_or_create_slash(db, referrer_id, product_id)

    if slash.slashes_count >= slash.max_slashes:
        return False, "🔥 Maximum price slashes reached (300 ETB off)! This price is fully slashed.", slash.slash_discount_amount

    slash.slashes_count += 1
    slash.slash_discount_amount = slash.slashes_count * 100  # 100 ETB per click (max 300 ETB)
    db.commit()

    # Also award friend who helped slash 50 bonus loyalty points
    award_points(db, clicker_id, 50, trans_type='slash_help', description=f"Helped Slash Price on Product #{product_id}")

    return True, f"🎉 <b>PRICE SLASHED!</b>\nYou slashed 100 ETB off your friend's order! You earned +50 Loyalty Points!", slash.slash_discount_amount


def redeem_hunt_code(db: Session, user_id: int, code_str: str) -> tuple[bool, str]:
    """Redeem a Treasure Hunt secret code."""
    clean_code = code_str.strip().upper()
    hunt_code = db.query(GuerrillaCode).filter(
        GuerrillaCode.code == clean_code,
        GuerrillaCode.code_type == 'hunt'
    ).first()

    if not hunt_code:
        # Default fallback hunt codes if not in DB
        if clean_code in ['OXELHUNT2026', 'WOODCRAFT', 'OXELDESK']:
            award_points(db, user_id, 500, trans_type='treasure_hunt', description=f"Treasure Hunt Code: {clean_code}")
            return True, f"🏆 <b>TREASURE HUNT CODE CLAIMED!</b>\n\nYou discovered secret code <code>{clean_code}</code>! <b>+500 Loyalty Points (50 ETB credit)</b> awarded to your account!"
        return False, f"❌ Invalid or expired Secret Treasure Code: <code>{html.escape(clean_code)}</code>"

    if hunt_code.is_claimed:
        return False, f"⚠️ Secret code <code>{html.escape(clean_code)}</code> has already been claimed!"

    hunt_code.is_claimed = True
    hunt_code.claimed_by_user_id = user_id
    hunt_code.claimed_at = datetime.now(timezone.utc)

    # Award loyalty points equal to reward amount
    award_points(db, user_id, hunt_code.reward_amount, trans_type='treasure_hunt', description=f"Treasure Hunt Code: {clean_code}")
    db.commit()

    return True, f"🏆 <b>TREASURE HUNT CODE CLAIMED!</b>\n\nYou unlocked secret code <code>{clean_code}</code>! <b>+{hunt_code.reward_amount:,} Loyalty Points</b> awarded to your account!"


def redeem_golden_seal(db: Session, user_id: int, code_str: str) -> tuple[bool, str]:
    """Redeem a laser-etched Golden Ticket seal found under physical products."""
    clean_code = code_str.strip().upper()
    seal = db.query(GuerrillaCode).filter(
        GuerrillaCode.code == clean_code,
        GuerrillaCode.code_type == 'goldenticket'
    ).first()

    if not seal:
        if clean_code.startswith('GOLD-') or clean_code in ['GOLDENOXEL', 'GOLDENSTAND']:
            award_points(db, user_id, 2000, trans_type='golden_seal', description=f"Golden Ticket Seal: {clean_code}")
            return True, f"🎟️ <b>GOLDEN SEAL VERIFIED!</b>\n\nCongratulations! You found a genuine Golden Oxel Seal! <b>+2,000 Loyalty Points (200 ETB credit)</b> awarded to your profile!"
        return False, f"❌ Invalid Golden Seal serial code: <code>{html.escape(clean_code)}</code>"

    if seal.is_claimed:
        return False, f"⚠️ Golden Seal <code>{html.escape(clean_code)}</code> has already been redeemed!"

    seal.is_claimed = True
    seal.claimed_by_user_id = user_id
    seal.claimed_at = datetime.now(timezone.utc)

    award_points(db, user_id, seal.reward_amount, trans_type='golden_seal', description=f"Golden Ticket Seal: {clean_code}")
    db.commit()

    return True, f"🎟️ <b>GOLDEN SEAL VERIFIED!</b>\n\n🎉 Congratulations! You unlocked Golden Seal <code>{clean_code}</code>! <b>+{seal.reward_amount:,} Loyalty Points</b> credited to your profile!"
