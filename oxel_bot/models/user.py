# User model is defined in database.py
# This module provides user-related helper functions

from database import SessionLocal, User


def sync_telegram_user(db: SessionLocal, tg_user) -> User:
    """
    Fetch or create User DB record and ALWAYS sync the latest username,
    first_name, and last_name from the live Telegram User object.
    """
    if not tg_user:
        return None

    user = db.query(User).filter(User.user_id == tg_user.id).first()

    # Fallback search by username if user_id matching failed
    if not user and tg_user.username:
        user = db.query(User).filter(User.username.ilike(tg_user.username.strip())).first()
        if user:
            user.user_id = tg_user.id

    if not user:
        user = User(
            user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name
        )
        db.add(user)
    else:
        # Always sync latest handle and names from Telegram
        if tg_user.username:
            user.username = tg_user.username
        if tg_user.first_name:
            user.first_name = tg_user.first_name
        if tg_user.last_name:
            user.last_name = tg_user.last_name

    db.commit()
    db.refresh(user)
    return user


def get_or_create_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Get existing user or create a new one, ensuring fields are updated."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user and username:
            user = db.query(User).filter(User.username.ilike(username.strip())).first()
            if user:
                user.user_id = user_id

        if not user:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            db.add(user)
        else:
            if username:
                user.username = username
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name

        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def update_user_address(user_id: int, phone: str = None, city: str = None, sub_city: str = None):
    """Update user's address information."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            if phone:
                user.phone = phone
            if city:
                user.city = city
            if sub_city:
                user.sub_city = sub_city
            db.commit()
    finally:
        db.close()
