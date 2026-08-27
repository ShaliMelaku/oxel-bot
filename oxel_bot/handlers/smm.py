import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal
from config import ADMIN_IDS, TELEGRAM_CHANNEL
from services.smm_service import generate_strategic_smm_post, publish_smm_post_to_channel
from utils.safe_message import safe_edit_text

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def smm_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin SMM Autonomous Control Center Hub."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    text = (
        "🤖 <b>AUTONOMOUS SUPERBOT SMM CONTROL CENTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 <b>Target Channel:</b> {TELEGRAM_CHANNEL}\n"
        "🧠 <b>Content Pillars Active:</b>\n"
        "• 🪵 <b>Craftsmanship & Timber Heritage</b> (30%)\n"
        "• 💡 <b>Ergonomics & Desk Transformations</b> (30%)\n"
        "• ✂️ <b>Guerrilla Viral Deals & Treasure Hunts</b> (20%)\n"
        "• ⭐ <b>Social Proof & Customer Reviews</b> (20%)\n\n"
        "Tap an action below to publish strategic content or write a custom channel post:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Publish Strategic SMM Post Now", callback_data="smm_publish_auto")],
        [InlineKeyboardButton("🪵 Publish Craftsmanship Story", callback_data="smm_publish_craftsmanship"),
         InlineKeyboardButton("💡 Publish Ergonomics Tip", callback_data="smm_publish_ergonomics")],
        [InlineKeyboardButton("✂️ Publish Guerrilla Deal", callback_data="smm_publish_guerrilla"),
         InlineKeyboardButton("⭐ Publish Social Proof", callback_data="smm_publish_social_proof")],
        [InlineKeyboardButton("✍️ Write Custom Channel Post", callback_data="smm_write_custom")],
        [InlineKeyboardButton("👀 Preview Next Strategic Post", callback_data="smm_preview")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")]
    ])

    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def smm_publish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pillar: str = None):
    """Handle publishing SMM post to Telegram Channel."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        ok, msg = await publish_smm_post_to_channel(context.bot, db, pillar=pillar)
        if update.callback_query:
            try:
                await update.callback_query.answer(msg, show_alert=True)
            except Exception:
                try:
                    await update.callback_query.message.reply_text(f"{msg}")
                except Exception:
                    pass
        await smm_admin_menu(update, context)
    except Exception as e:
        logger.exception("Error publishing SMM post: %s", e)
        if update.callback_query:
            try:
                await update.callback_query.message.reply_text(f"❌ SMM Publishing Error: {e}")
            except Exception:
                pass
    finally:
        db.close()


async def smm_preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Preview next strategic SMM post before broadcasting."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        text, keyboard, img_path = generate_strategic_smm_post(db)

        preview_text = (
            "👀 <b>STRATEGIC SMM POST PREVIEW</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n" + text
        )

        kb_list = keyboard.inline_keyboard if keyboard else []
        kb_list.append([InlineKeyboardButton("🚀 Publish This Post Now", callback_data="smm_publish_auto")])
        kb_list.append([InlineKeyboardButton("🔙 SMM Hub", callback_data="smm_admin_menu")])

        await safe_edit_text(update, context, preview_text, InlineKeyboardMarkup(kb_list), parse_mode="HTML")
    finally:
        db.close()


async def smm_write_custom_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt admin to type custom post text for channel broadcast."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    context.user_data['awaiting_custom_smm_text'] = True
    text = (
        "✍️ <b>WRITE CUSTOM SMM CHANNEL POST</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Please type your custom announcement message in chat below.\n"
        "The bot will automatically attach a shop buy button link and publish it directly to your Telegram Channel!"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="smm_admin_menu")]])
    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")
