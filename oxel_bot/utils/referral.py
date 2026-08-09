"""Referral link utilities for Oxel bot."""
import logging
from database import SessionLocal
from services.referral_service import register_referral as service_register_referral

logger = logging.getLogger(__name__)


def parse_referral_code(arg: str) -> int | None:
    """Extract referrer user_id from ?start=ref_USERID deep link argument."""
    if arg and arg.startswith("ref_"):
        try:
            return int(arg[4:])
        except (ValueError, TypeError):
            return None
    return None


def register_referral(new_user_id: int, referrer_id: int) -> bool:
    """Register referral relationship using dedicated Referral service and model."""
    db = SessionLocal()
    try:
        return service_register_referral(db, new_user_id, referrer_id)
    except Exception:
        logger.exception(f"Error registering referral for new user {new_user_id} by {referrer_id}")
        return False
    finally:
        db.close()
