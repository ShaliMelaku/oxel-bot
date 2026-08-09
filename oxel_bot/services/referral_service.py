import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import User, Referral
from services.loyalty_service import award_points

logger = logging.getLogger(__name__)

REFERRAL_BONUS_POINTS = 500


def register_referral(db: Session, new_user_id: int, referrer_id: int) -> bool:
    """
    Register referral link between new user and referrer.
    Prevents self-referrals and duplicate referral assignments.
    """
    if new_user_id == referrer_id:
        logger.warning(f"Self-referral attempt blocked for user {new_user_id}")
        return False

    referrer = db.query(User).filter(User.user_id == referrer_id).first()
    if not referrer:
        logger.warning(f"Referral failed: Referrer {referrer_id} does not exist")
        return False

    existing_ref = db.query(Referral).filter(Referral.referred_user_id == new_user_id).first()
    if existing_ref:
        logger.warning(f"Referral failed: User {new_user_id} already has a referral record")
        return False

    referral = Referral(
        referrer_id=referrer_id,
        referred_user_id=new_user_id,
        status='pending',
        reward_awarded=False
    )
    db.add(referral)

    new_user = db.query(User).filter(User.user_id == new_user_id).first()
    if new_user:
        new_user.referred_by = referrer_id

    db.commit()
    logger.info(f"Referral registered: User {new_user_id} referred by {referrer_id}")
    return True


def complete_referral_reward(db: Session, referred_user_id: int) -> bool:
    """
    Award referral bonus to referrer once the referred user completes their first order.
    Ensures rewards are awarded exactly once.
    """
    referral = db.query(Referral).filter(
        Referral.referred_user_id == referred_user_id,
        Referral.status == 'pending',
        Referral.reward_awarded == False
    ).first()

    if not referral:
        return False

    referral.status = 'completed'
    referral.reward_awarded = True
    referral.completed_at = datetime.now()

    # Award points to referrer
    award_points(
        db,
        user_id=referral.referrer_id,
        points=REFERRAL_BONUS_POINTS,
        trans_type='referral_bonus',
        description=f"Referral bonus for inviting user #{referred_user_id}"
    )

    db.commit()
    logger.info(f"Referral reward completed: Referrer {referral.referrer_id} awarded {REFERRAL_BONUS_POINTS} pts")
    return True
