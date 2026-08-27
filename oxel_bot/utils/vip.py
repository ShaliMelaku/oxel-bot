"""VIP Tier calculation, loyalty points synchronization, and perk management module."""
from sqlalchemy import func
from database import SessionLocal, User, Order, LoyaltyTransaction


def sync_user_loyalty_and_vip(db, user_id: int) -> dict:
    """
    Synchronize user's total spend, loyalty points (from transactions, spend & admin awards),
    and VIP tier with DB state.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return {
            "tier": "Bronze 🥉",
            "total_spend": 0,
            "next_tier": "Silver 🥈",
            "needed": 5000,
            "perk": "Standard Customer",
            "points": 0
        }

    # 1. Sum points from all LoyaltyTransactions (admin adjustments, referral rewards, redemptions)
    tx_points = db.query(func.sum(LoyaltyTransaction.points)).filter(
        LoyaltyTransaction.user_id == user_id
    ).scalar() or 0

    # 2. Calculate verified order spend & points from completed purchases
    total_spend = db.query(func.sum(Order.total_price)).filter(
        Order.user_id == user_id,
        Order.status.in_(['paid', 'confirmed', 'shipped', 'delivered'])
    ).scalar() or 0

    order_earned_pts = total_spend * 4  # 4 points per 1 ETB (1 pt per 0.25 ETB)

    # Combined true points balance = max of stored points, transaction sum, or spend-earned points + transactions
    current_stored = user.loyalty_points or 0
    synced_points = max(current_stored, tx_points, tx_points + order_earned_pts)

    if user.loyalty_points != synced_points:
        user.loyalty_points = synced_points

    # 3. Calculate VIP Tier
    if total_spend >= 15000 or synced_points >= 15000:
        tier = "Gold 🥇"
        next_tier = "MAX VIP"
        needed = 0
        perk = "🎁 Free Custom Engraving (+400 ETB waived) + 1.5x Points Bonus!"
    elif total_spend >= 5000 or synced_points >= 5000:
        tier = "Silver 🥈"
        next_tier = "Gold 🥇"
        needed = 15000 - total_spend
        perk = "🎁 1.2x Loyalty Points Bonus on all orders!"
    else:
        tier = "Bronze 🥉"
        next_tier = "Silver 🥈"
        needed = 5000 - total_spend
        perk = "🎁 Standard Loyalty Rewards (1 pt per 1 ETB)"

    if user.vip_tier != tier:
        user.vip_tier = tier

    db.commit()

    return {
        "tier": tier,
        "total_spend": total_spend,
        "next_tier": next_tier,
        "needed": max(0, needed),
        "perk": perk,
        "points": user.loyalty_points or 0
    }


def get_user_vip_info(user_id: int) -> dict:
    db = SessionLocal()
    try:
        return sync_user_loyalty_and_vip(db, user_id)
    finally:
        db.close()
