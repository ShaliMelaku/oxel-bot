import html
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from database import SessionLocal, User
from services.cart_service import get_cart_summary
from services.promo_service import validate_promo_code
from utils.safe_message import safe_edit_text

logger = logging.getLogger(__name__)


async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start checkout — reads from persistent DB cart."""
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        from models.user import sync_telegram_user
        sync_telegram_user(db, update.effective_user)
        summary = get_cart_summary(db, user_id)

        if not summary['items']:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Browse Products", callback_data="catalog")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])
            if update.callback_query:
                await safe_edit_text(update, context, "🛒 <b>Your Cart is Empty</b>\n\nAdd items before checking out.", kb, parse_mode="HTML")
            return

        # Re-validate promo against fresh DB cart total
        promo_code = context.user_data.get('applied_promo')
        discount_amount = 0
        if promo_code:
            res = validate_promo_code(db, promo_code, user_id, summary['subtotal'])
            if res['valid']:
                discount_amount = res['discount_amount']
            else:
                context.user_data.pop('applied_promo', None)
                promo_code = None

        total = max(0, summary['subtotal'] - discount_amount)
        context.user_data['cart_total'] = total
        context.user_data['discount_amount'] = discount_amount

        # Build itemized summary
        items_lines = []
        for item in summary['items']:
            var_parts = []
            if item.get('finish_name'):
                var_parts.append(html.escape(item['finish_name']))
            if item.get('size_name'):
                var_parts.append(f"Size: {html.escape(item['size_name'])}")
            var_str = f" ({', '.join(var_parts)})" if var_parts else ""
            eng_line = (
                f"\n    ✨ Engraving: <code>{html.escape(item['customization'])}</code>"
                if item.get('customization') and not item['customization'].startswith('[')
                else ""
            )
            oos = " ⚠️ OOS" if not item['stock_available'] else ""
            items_lines.append(
                f"  • {item['quantity']}× {html.escape(item['product_name'])}{var_str}{oos} — {item['subtotal']:,} ETB{eng_line}"
            )

        items_text = "\n".join(items_lines)
        discount_line = f"\n🎟️ <b>Promo ({html.escape(str(promo_code))}):</b> -{discount_amount:,} ETB" if discount_amount > 0 else ""

        text = (
            f"💳 <b>Checkout</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Order Summary:</b>\n{items_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━{discount_line}\n"
            f"💰 <b>Total: {total:,} ETB</b>\n\n"
            f"📍 <b>Please enter your shipping address:</b>\n"
            f"• Type your address below, OR\n"
            f"• Tap \"📍 Share My Location\" to share GPS\n\n"
            f"<i>Format: City, Sub-city, Phone Number</i>\n"
            f"<i>Example: Addis Ababa, Bole, 0912345678</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Cart", callback_data="view_cart")]
        ])

        # Safe edit handles both photo and text messages
        await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")

        from utils.keyboards import address_input_reply_keyboard
        user_rec = db.query(User).filter(User.user_id == user_id).first()
        saved_1 = user_rec.saved_address_1 if user_rec else None
        saved_2 = user_rec.saved_address_2 if user_rec else None
        context.user_data['saved_addr1_full'] = saved_1
        context.user_data['saved_addr2_full'] = saved_2

        loc_kb = address_input_reply_keyboard(saved_1, saved_2)

        if update.callback_query:
            await update.callback_query.message.reply_text(
                "👇 Tap a saved address below, share your location, or type a new address:",
                reply_markup=loc_kb
            )
        else:
            await update.message.reply_text(
                "👇 Tap a saved address below, share your location, or type a new address:",
                reply_markup=loc_kb
            )

        context.user_data['awaiting_address'] = True

    except Exception as e:
        logger.exception("Checkout error")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Back to Cart", callback_data="view_cart")]
        ])
        if update.callback_query:
            try:
                await update.callback_query.message.reply_text(
                    "⚠️ <b>Checkout error.</b> Please try again.",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception:
                pass
    finally:
        db.close()


async def process_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive typed/shared address, show delivery slot picker."""
    address = update.message.text
    context.user_data['shipping_address'] = address
    context.user_data['awaiting_address'] = False

    # Persist address to user profile
    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        saved_phone = None
        if user:
            user.saved_address_1 = address
            saved_phone = user.phone
            db.commit()
    finally:
        db.close()

    from utils.keyboards import phone_input_reply_keyboard
    kb = phone_input_reply_keyboard(saved_phone)

    text = (
        f"📍 <b>Shipping Address Confirmed</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{html.escape(address)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📞 <b>Contact Phone Number Required</b>\n"
        f"Our courier & store team need a phone number to contact you upon delivery.\n\n"
        f"👇 Tap below to share your contact or use saved phone, or type a new phone number:"
    )

    await update.message.reply_text(
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )
    context.user_data['awaiting_phone'] = True


async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive shared/typed contact phone number, proceed to delivery slot picker."""
    user_id = update.effective_user.id
    phone = None

    if update.message and update.message.contact:
        phone = update.message.contact.phone_number
    elif update.message and update.message.text:
        raw_text = update.message.text.strip()
        for prefix in ("📱 Use Saved Phone:", "📱 "):
            if raw_text.startswith(prefix):
                raw_text = raw_text.replace(prefix, "").strip()
        phone = raw_text

    if not phone or len(phone) < 7:
        phone = "0900000000"

    context.user_data['shipping_phone'] = phone
    context.user_data['awaiting_phone'] = False

    # Persist phone to DB
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.phone = phone
            db.commit()
    finally:
        db.close()

    text = (
        f"📞 <b>Contact Phone Saved:</b> <code>{html.escape(phone)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🚚 <b>Select Your Preferred Delivery Time Slot:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 Morning (9 AM – 12 PM)", callback_data="slot_morning")],
        [InlineKeyboardButton("☀️ Afternoon (2 PM – 5 PM)", callback_data="slot_afternoon")],
        [InlineKeyboardButton("🌙 Evening (5 PM – 8 PM)", callback_data="slot_evening")],
        [InlineKeyboardButton("✏️ Re-enter Address", callback_data="edit_address"),
         InlineKeyboardButton("🛒 Back to Cart", callback_data="view_cart")]
    ])

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def confirm_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show payment method selection after delivery slot chosen."""
    query = update.callback_query
    user_id = update.effective_user.id

    # Re-fetch cart total from DB in case session was lost
    cart_total = context.user_data.get('cart_total')
    if not cart_total:
        db = SessionLocal()
        try:
            summary = get_cart_summary(db, user_id)
            promo_code = context.user_data.get('applied_promo')
            discount = 0
            if promo_code:
                res = validate_promo_code(db, promo_code, user_id, summary['subtotal'])
                if res['valid']:
                    discount = res['discount_amount']
            cart_total = max(0, summary['subtotal'] - discount)
            context.user_data['cart_total'] = cart_total
            context.user_data['discount_amount'] = discount
        finally:
            db.close()

    discount = context.user_data.get('discount_amount', 0)
    promo_code = context.user_data.get('applied_promo', '')
    slot = context.user_data.get('delivery_slot', 'Morning (9 AM – 12 PM)')
    address = context.user_data.get('shipping_address', 'Not set')
    phone = context.user_data.get('shipping_phone', 'Not set')

    discount_line = f"\n🎟️ <b>Promo ({html.escape(str(promo_code))}):</b> -{discount:,} ETB" if promo_code else ""

    text = (
        f"💳 <b>Choose Payment Method</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Amount Due:</b> {cart_total:,} ETB{discount_line}\n"
        f"📞 <b>Contact Phone:</b> <code>{html.escape(phone)}</code>\n"
        f"🚚 <b>Delivery Slot:</b> <i>{html.escape(slot)}</i>\n"
        f"📍 <b>Address:</b> <i>{html.escape(address)}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Select your preferred payment method:"
    )

    db = SessionLocal()
    pts = 0
    try:
        from utils.vip import sync_user_loyalty_and_vip
        vdata = sync_user_loyalty_and_vip(db, user_id)
        pts = vdata.get('points', 0)
    finally:
        db.close()

    pts_btn = InlineKeyboardButton(f"🏅 Loyalty Points ({pts:,} pts)", callback_data="pay_points")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Telebirr", callback_data="pay_telebirr"),
         InlineKeyboardButton("🏦 CBE Mobile", callback_data="pay_cbe")],
        [pts_btn],
        [InlineKeyboardButton("✏️ Change Address", callback_data="edit_address"),
         InlineKeyboardButton("🛒 Back to Cart", callback_data="view_cart")]
    ])

    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")
