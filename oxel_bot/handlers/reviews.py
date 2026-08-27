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

        await query.edit_message_text(
            f"""🎉 *Thank You For Your Review!*
━━━━━━━━━━━━━━━━━━━━
Your rating: {stars_str} ({rating}/5 stars)

Your feedback helps us continuously perfect our handcrafted woodwork! 🪵✨""",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]),
            parse_mode="Markdown"
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
