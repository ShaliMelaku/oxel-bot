import logging
from sqlalchemy.orm import Session
from database import User, LoyaltyTransaction

logger = logging.getLogger(__name__)


def award_points(db: Session, user_id: int, points: int, trans_type: str, description: str, order_id: int = None) -> bool:
    """
    Award or deduct loyalty points for a user with full audit logging.
    Prevents negative balances.
    """
    if points == 0:
        return True

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.error(f"Failed to process loyalty points: User {user_id} not found")
        return False

    current_balance = user.loyalty_points or 0
    if points < 0 and (current_balance + points) < 0:
        logger.warning(f"Loyalty deduction rejected for user {user_id}: Insufficient points ({current_balance} available, {abs(points)} requested)")
        return False

    user.loyalty_points = current_balance + points

    # Update VIP tier if points increased
    if user.loyalty_points >= 3750:
        user.vip_tier = "Gold 🥇"
    elif user.loyalty_points >= 1250:
        user.vip_tier = "Silver 🥈"
    else:
        user.vip_tier = "Bronze 🥉"

    transaction = LoyaltyTransaction(
        user_id=user_id,
        points=points,
        type=trans_type,
        description=description,
        order_id=order_id
    )
    db.add(transaction)
    db.commit()
    return True


def get_user_loyalty_history(db: Session, user_id: int, limit: int = 20) -> list:
    """Get audit history of loyalty transactions for a user."""
    return db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.user_id == user_id
    ).order_by(LoyaltyTransaction.created_at.desc()).limit(limit).all()
