"""Product Reviews & Ratings Handler Module."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, Order, Product


async def prompt_order_rating(update: Update, context: ContextTypes.DEFAULT_TYPE, order_number: str):
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_number == order_number).first()
        if not order:
            return

        product = db.query(Product).filter(Product.id == order.product_id).first()
        prod_name = product.name if product else "your item"

        text = f"""⭐ *Rate Your Product Experience!*
━━━━━━━━━━━━━━━━━━━━
Order: `{order_number}`
Item: *{prod_name}*

How would you rate your handcrafted wooden accessory?"""

        keyboard = [
            [
                InlineKeyboardButton("⭐ 1", callback_data=f"rate_{order.id}_1"),
                InlineKeyboardButton("⭐ 2", callback_data=f"rate_{order.id}_2"),
                InlineKeyboardButton("⭐ 3", callback_data=f"rate_{order.id}_3"),
                InlineKeyboardButton("⭐ 4", callback_data=f"rate_{order.id}_4"),
                InlineKeyboardButton("⭐ 5", callback_data=f"rate_{order.id}_5")
            ],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                )
            except Exception:
                await update.callback_query.message.reply_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
    finally:
        db.close()


async def process_rating(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int, rating: int):
    query = update.callback_query
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            await query.answer("Order not found!")
            return

        order.review_rating = rating
        db.commit()

        # Recalculate Product Average Rating
        product = db.query(Product).filter(Product.id == order.product_id).first()
        if product:
            all_ratings = [o.review_rating for o in db.query(Order).filter(
                Order.product_id == product.id,
                Order.review_rating.isnot(None)
            ).all()]

            if all_ratings:
                product.avg_rating = round(sum(all_ratings) / len(all_ratings), 1)
                product.review_count = len(all_ratings)
                db.commit()

        stars_str = "⭐" * rating
        await query.answer(f"Thank you for rating {stars_str}!", show_alert=True)

        if rating >= 4:
            tip_keyboard = [
                [
                    InlineKeyboardButton("☕ 50 ETB", callback_data=f"tip_{order.id}_50"),
                    InlineKeyboardButton("🪵 100 ETB", callback_data=f"tip_{order.id}_100"),
                    InlineKeyboardButton("🌟 200 ETB", callback_data=f"tip_{order.id}_200")
                ],
                [InlineKeyboardButton("✍️ Custom Tip Amount", callback_data=f"tip_{order.id}_custom")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]

            await query.edit_message_text(
                f"🎉 <b>Thank You For Your Review!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Your rating: {stars_str} ({rating}/5 stars)\n\n"
                f"Your feedback helps us continuously perfect our handcrafted woodwork! 🪵✨\n\n"
                f"💖 <b>Tip Our Craftsmen & Courier Team</b>\n"
                f"Loved your experience? Support our local Ethiopian artisans with a small tip! ☕",
                reply_markup=InlineKeyboardMarkup(tip_keyboard),
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text(
                f"🎉 <b>Thank You For Your Review!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Your rating: {stars_str} ({rating}/5 stars)\n\n"
                f"Your feedback helps us continuously perfect our handcrafted woodwork! 🪵✨",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]),
                parse_mode="HTML"
            )

        # Notify admins instantly about the new review
        try:
            import html
            from config import ADMIN_IDS
            from database import User
            customer = db.query(User).filter(User.user_id == order.user_id).first()
            cust_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip() if customer else "Customer"
            username_str = f" (@{customer.username})" if customer and customer.username else ""
            prod_name = product.name if product else "Wooden Accessory"
            avg_str = f"{product.avg_rating} ⭐ ({product.review_count} reviews)" if product else "N/A"

            admin_text = (
                f"🌟 <b>NEW CUSTOMER REVIEW RECEIVED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔢 <b>Order #:</b> <code>{html.escape(order.order_number)}</code>\n"
                f"👤 <b>Customer:</b> {html.escape(cust_name)}{html.escape(username_str)}\n"
                f"📦 <b>Product:</b> {html.escape(prod_name)}\n"
                f"⭐ <b>Rating:</b> {stars_str} ({rating}/5 Stars)\n"
                f"📊 <b>Product Rating Avg:</b> {avg_str}"
            )

            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        except Exception:
            pass
    finally:
        db.close()


async def handle_tip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int, amt_str: str):
    query = update.callback_query
    from utils.safe_message import safe_edit_text
    import html

    if amt_str == 'custom':
        context.user_data['awaiting_custom_tip_amount'] = True
        context.user_data['awaiting_tip_order_id'] = order_id
        text = (
            "💖 <b>Custom Tip Amount</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please type your custom tip amount in ETB (numbers only, e.g. 150):"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
        await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")
        return

    try:
        amount = int(amt_str)
    except ValueError:
        amount = 100

    await render_tip_payment_instructions(update, context, order_id, amount)


async def render_tip_payment_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int, amount: int):
    import html
    from config import TELEBIRR_NUMBER, CBE_NUMBER
    from utils.safe_message import safe_edit_text

    context.user_data['awaiting_tip_order_id'] = order_id
    context.user_data['tip_amount'] = amount

    db = SessionLocal()
    ord_num = "N/A"
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            ord_num = order.order_number
    finally:
        db.close()

    text = (
        f"💖 <b>Craftsman & Courier Tip — {amount:,} ETB</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Order: <code>{html.escape(ord_num)}</code>\n\n"
        f"Thank you for your generosity! Our craftsmen & delivery team truly appreciate your support. 🙏\n\n"
        f"<b>Please transfer {amount:,} ETB via Telebirr or CBE:</b>\n\n"
        f"📱 <b>Telebirr:</b> <code>{html.escape(TELEBIRR_NUMBER)}</code>\n"
        f"🏦 <b>CBE Account:</b> <code>{html.escape(CBE_NUMBER)}</code>\n\n"
        f"👇 Send your transaction reference number or a receipt photo below to confirm your tip:"
    )

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
    if update.callback_query:
        await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


async def process_tip_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, ref_or_note: str = None):
    order_id = context.user_data.pop('awaiting_tip_order_id', None)
    amount = context.user_data.pop('tip_amount', 100)
    context.user_data.pop('awaiting_custom_tip_amount', None)

    ref_text = ref_or_note or (update.message.text.strip() if update.message and update.message.text else "Photo Receipt")

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first() if order_id else None
        ord_num = order.order_number if order else "N/A"

        # Notify user
        await update.message.reply_text(
            f"💖 <b>Tip Received — Thank You!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Your tip of <b>{amount:,} ETB</b> for Order <code>{ord_num}</code> has been received!\n"
            f"Our craftsmen and courier team send you their heartfelt gratitude! 🪵☕✨",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]),
            parse_mode="HTML"
        )

        # Notify admins
        import html
        from config import ADMIN_IDS
        from database import User
        user_id = update.effective_user.id
        customer = db.query(User).filter(User.user_id == user_id).first()
        cust_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip() if customer else "Customer"
        username_str = f" (@{customer.username})" if customer and customer.username else ""

        admin_text = (
            f"💖 <b>NEW CRAFTSMAN & COURIER TIP RECEIVED!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 <b>Order #:</b> <code>{html.escape(ord_num)}</code>\n"
            f"👤 <b>Customer:</b> {html.escape(cust_name)}{html.escape(username_str)}\n"
            f"☕ <b>Tip Amount:</b> {amount:,} ETB\n"
            f"📝 <b>Ref / Note:</b> <code>{html.escape(ref_text)}</code>"
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_text, parse_mode="HTML")
            except Exception:
                pass
    finally:
        db.close()
