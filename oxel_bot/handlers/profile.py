"""Customer Profile & Saved Addresses Handler Module."""
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, User, Order
from utils.vip import get_user_vip_info
from utils.analytics import get_customer_analytics


async def user_profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    try:
        from models.user import sync_telegram_user
        db_user = sync_telegram_user(db, user)

        from utils.vip import sync_user_loyalty_and_vip
        vip_info = sync_user_loyalty_and_vip(db, user.id)
        stats = get_customer_analytics(user.id)

        # Refresh db_user to get synced fields
        db_user = db.query(User).filter(User.user_id == user.id).first()

        addr1 = html.escape(db_user.saved_address_1 or "Not saved yet")
        addr2 = html.escape(db_user.saved_address_2 or "Not saved yet")

        # Real customer identity from live Telegram object
        first_name = html.escape(user.first_name or '')
        last_name = html.escape(user.last_name or '')
        full_name = f"{first_name} {last_name}".strip()
        handle = f"@{html.escape(user.username)}" if user.username else "<i>no username set</i>"

        text = (
            f"👤 <b>YOUR CUSTOMER PROFILE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Name:</b> {full_name}\n"
            f"💬 <b>Telegram Handle:</b> {handle}\n"
            f"🏅 <b>VIP Status:</b> <b>{html.escape(vip_info['tier'])}</b>\n"
            f"🎁 <b>VIP Perk:</b> <i>{html.escape(vip_info['perk'])}</i>\n\n"
            f"📊 <b>Personal Store Analytics:</b>\n"
            f"  • Total Orders Placed: <b>{stats['total_orders']}</b>\n"
            f"  • Total Verified Spend: <b>{stats['total_spend']:,} ETB</b>\n"
            f"  • Loyalty Points Balance: <b>{stats['loyalty_points']:,} pts</b>\n"
            f"  🌱 <i>Eco Impact: Saved <b>{stats['co2_saved_kg']} kg CO2</b> choosing solid wood!</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Saved Shipping Addresses:</b>\n"
            f"1️⃣ <b>Primary:</b> <i>{addr1}</i>\n"
            f"2️⃣ <b>Secondary:</b> <i>{addr2}</i>"
        )

        keyboard = [
            [InlineKeyboardButton("✏️ Edit Address #1", callback_data="edit_saved_addr_1"),
             InlineKeyboardButton("✏️ Edit Address #2", callback_data="edit_saved_addr_2")],
            [InlineKeyboardButton("🏅 Loyalty & Referral Rewards", callback_data="loyalty_menu")],
            [InlineKeyboardButton("📦 My Orders Log", callback_data="my_orders")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                )
            except Exception:
                await update.callback_query.message.reply_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                )
        else:
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
            )
    finally:
        db.close()
