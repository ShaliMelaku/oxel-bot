"""
Loyalty Points & Referral System Handler (Method 2 Policy)
- 1 point per 100 ETB spent
- Redeem points for discounts (100 pts = 100 ETB off)
- Unique referral links (t.me/OxelShopBot?start=ref_USERID)
- Referrer gets +100 points (100 ETB) when friend completes first purchase
- Referred friend gets 5% Welcome Discount!
"""
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, User, Order


async def loyalty_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    try:
        from models.user import sync_telegram_user
        db_user = sync_telegram_user(db, user)

        from utils.vip import sync_user_loyalty_and_vip
        vip_info = sync_user_loyalty_and_vip(db, user.id)

        db_user = db.query(User).filter(User.user_id == user.id).first()
        points = db_user.loyalty_points if (db_user and db_user.loyalty_points is not None) else 0

        # Calculate total spend
        total_spend = sum(
            o.total_price for o in db.query(Order).filter(
                Order.user_id == user.id,
                Order.status.in_(['paid', 'confirmed', 'shipped', 'delivered'])
            ).all()
        )
        redeemable = (points // 100) * 100  # 100 pts = 100 ETB

        bot_username = context.bot.username or "OxelShopBot"
        referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

        # Real customer handle from live Telegram object
        handle = f"@{html.escape(user.username)}" if user.username else html.escape(user.first_name or f"ID:{user.id}")

        text = (
            f"🎁 <b>LOYALTY &amp; REFERRAL REWARDS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 <b>Your Handle:</b> {handle}\n\n"
            f"🏅 <b>Your Loyalty Points:</b> <code>{points:,} pts</code>\n"
            f"💰 <b>Total Store Spend:</b> {total_spend:,} ETB\n"
            f"🎟️ <b>Redeemable Discount:</b> {redeemable:,} ETB\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>STORE LOYALTY POLICY:</b>\n"
            f"• Earn <b>1 point</b> for every 100 ETB spent\n"
            f"• Redeem <b>100 points = 100 ETB off</b> your next order\n"
            f"• Use <code>MYPOINTS</code> at checkout promo field to redeem\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤝 <b>REFER &amp; EARN POLICY:</b>\n"
            f"🔗 <b>Your Personal Referral Link:</b>\n"
            f"<code>{html.escape(referral_link)}</code>\n\n"
            f"<b>How Referral Rewards Work:</b>\n"
            f"1️⃣ Share your link with friends, family, or colleagues\n"
            f"2️⃣ When your friend joins, they get <b>5% WELCOME DISCOUNT</b> on their first order\n"
            f"3️⃣ When their first order is verified, YOU get <b>+100 LOYALTY POINTS (100 ETB)</b> automatically!\n"
            f"4️⃣ Unlimited referrals — no maximum cap!"
        )

        keyboard = []
        if redeemable > 0:
            keyboard.append([InlineKeyboardButton(f"🎟️ Redeem {redeemable:,} ETB Points at Checkout", callback_data="redeem_points")])
        keyboard.append([InlineKeyboardButton("📦 Browse Catalog & Shop", callback_data="catalog")])
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                )
            except Exception:
                try:
                    await update.callback_query.message.delete()
                except Exception:
                    pass
                await update.callback_query.message.reply_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                )
        else:
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
            )
    finally:
        db.close()


def award_loyalty_points(user_id: int, amount_spent: int):
    """Award 1 point per 100 ETB spent after successful order."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            points_earned = amount_spent // 100
            user.loyalty_points = (user.loyalty_points or 0) + points_earned
            db.commit()
            return points_earned
        return 0
    finally:
        db.close()


def award_referral_bonus(referrer_id: int, new_user_id: int):
    """Award +100 referral bonus points to referrer when referred user completes first order."""
    db = SessionLocal()
    try:
        first_order_count = db.query(Order).filter(
            Order.user_id == new_user_id,
            Order.status.in_(['paid', 'confirmed', 'shipped', 'delivered'])
        ).count()

        if first_order_count == 1:
            # Award referrer +100 points (100 ETB value)
            referrer = db.query(User).filter(User.user_id == referrer_id).first()
            if referrer:
                referrer.loyalty_points = (referrer.loyalty_points or 0) + 100

            # Award referred user +50 points
            new_user = db.query(User).filter(User.user_id == new_user_id).first()
            if new_user:
                new_user.loyalty_points = (new_user.loyalty_points or 0) + 50

            db.commit()
            return True
        return False
    finally:
        db.close()


def redeem_points_for_discount(user_id: int) -> int:
    """Convert all redeemable loyalty points to ETB discount, reset points."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user or not user.loyalty_points:
            return 0
        redeemable = (user.loyalty_points // 100) * 100
        discount = redeemable
        user.loyalty_points = user.loyalty_points - redeemable
        db.commit()
        return discount
    finally:
        db.close()
