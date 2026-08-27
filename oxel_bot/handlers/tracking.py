import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, Order, OrderStatusHistory, Product
from utils.keyboards import main_menu_keyboard, order_status_keyboard
from utils.safe_message import safe_edit_text


async def track_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "<b>🔍 Track Your Order</b>\n\nPlease enter your order number:\n<i>Example: OXEL-ABC123</i>"
    back_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 My Orders", callback_data="my_orders"),
         InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])

    if update.callback_query:
        await safe_edit_text(update, context, text, back_kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=back_kb, parse_mode="HTML")

    context.user_data['awaiting_tracking'] = True


async def process_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_number = update.message.text.strip().lstrip('#').replace(' ', '').upper()
    context.user_data['awaiting_tracking'] = False

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_number == order_number).first()

        if not order:
            await update.message.reply_text(
                "❌ <b>Order not found.</b>\n\nPlease double-check your order number and try again.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 My Orders", callback_data="my_orders"),
                     InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
            return

        await show_order_status(update, context, order_number)
    finally:
        db.close()


async def show_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE, order_number: str):
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_number == order_number).first()

        if not order:
            msg = update.effective_message or (update.callback_query.message if update.callback_query else None)
            if msg:
                await msg.reply_text(
                    "❌ Order not found.",
                    reply_markup=main_menu_keyboard()
                )
            return

        history = db.query(OrderStatusHistory).filter(
            OrderStatusHistory.order_id == order.id
        ).order_by(OrderStatusHistory.created_at.asc()).all()

        status_emoji = {
            'pending': '⏳', 'submitted': '⏳', 'paid': '✅', 'verified': '✅', 'confirmed': '📦',
            'shipped': '🚚', 'delivered': '🏠', 'cancelled': '❌', 'rejected': '❌'
        }

        # Progress tracking steps
        if order.status in ['cancelled', 'rejected']:
            progress = "❌ ORDER REJECTED / CANCELLED"
        else:
            statuses = ['pending', 'submitted', 'verified', 'confirmed', 'shipped', 'delivered']
            current_idx = statuses.index(order.status) if order.status in statuses else 1
            progress_bar = ''.join(['●' if i <= current_idx else '○' for i in range(len(statuses))])
            progress = f"{progress_bar}\n<i>Submitted → Verified → Shipped → Delivered</i>"

        timeline = []
        for h in history:
            emoji = status_emoji.get(h.status, '📌')
            date_str = h.created_at.strftime('%b %d, %Y · %I:%M %p')
            timeline.append(f"  {emoji} <b>{h.status.upper()}</b> — {date_str}")
            if h.note:
                timeline.append(f"     <i>{html.escape(h.note)}</i>")

        if order.items:
            items_summary = ", ".join([f"{item.quantity}x {html.escape(item.product_name)}" for item in order.items])
        else:
            product = db.query(Product).filter(Product.id == order.product_id).first()
            items_summary = html.escape(product.name) if product else 'N/A'

        text = (
            f"<b>📦 Order Status Log</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 <b>Order:</b> <code>{html.escape(order.order_number)}</code>\n"
            f"📦 <b>Items:</b> {items_summary}\n"
            f"💰 <b>Total:</b> {order.total_price:,} ETB\n"
            f"💳 <b>Payment:</b> {html.escape((order.payment_method or 'N/A').upper())}\n"
            f"📌 <b>Status:</b> {status_emoji.get(order.status, '📌')} <b>{order.status.upper()}</b>\n"
            f"🚚 <b>Tracking:</b> <code>{html.escape(order.tracking_number or 'Not yet assigned')}</code>\n\n"
            f"<b>Progress:</b>\n{progress}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Timeline History:</b>\n"
            f"{chr(10).join(timeline) if timeline else '  <i>No updates yet</i>'}"
        )

        keyboard = order_status_keyboard(order_number, is_delivered=(order.status == 'delivered'))

        if update.callback_query:
            await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")
        else:
            await update.effective_message.reply_text(
                text, reply_markup=keyboard, parse_mode="HTML"
            )
    finally:
        db.close()


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        orders = db.query(Order).filter(
            Order.user_id == user_id
        ).order_by(Order.created_at.desc()).limit(10).all()

        if not orders:
            text = "📭 <b>You have no orders yet.</b>\n\nBrowse our catalog to place your first order!"
            keyboard = [[InlineKeyboardButton("📦 Browse Products", callback_data="catalog")]]
        else:
            status_emoji = {
                'pending': '⏳', 'submitted': '⏳', 'paid': '✅', 'verified': '✅', 'confirmed': '📦',
                'shipped': '🚚', 'delivered': '🏠', 'cancelled': '❌', 'rejected': '❌'
            }

            text = f"<b>📋 Your Orders</b> ({len(orders)})\n━━━━━━━━━━━━━━━━━━━━\n"
            for order in orders:
                if order.items:
                    items_desc = ", ".join([f"{item.quantity}x {html.escape(item.product_name)}" for item in order.items])
                else:
                    product = db.query(Product).filter(Product.id == order.product_id).first()
                    items_desc = html.escape(product.name) if product else 'Item'

                emoji = status_emoji.get(order.status, '📌')
                rating_str = f" · ⭐ {order.review_rating}/5" if order.review_rating else ""
                text += f"\n{emoji} <code>{html.escape(order.order_number)}</code>{rating_str}\n"
                text += f"   📦 {items_desc} · <b>{order.total_price:,} ETB</b>\n"
                text += f"   📌 {order.status.upper()} · {order.created_at.strftime('%b %d, %Y')}\n"

            keyboard = []
            for order in orders:
                row = [InlineKeyboardButton(
                    f"🔍 {order.order_number}",
                    callback_data=f"refresh_order_{order.order_number}"
                )]
                if order.status == 'delivered':
                    btn_label = f"⭐ {order.review_rating}/5" if order.review_rating else "⭐ Review"
                    row.append(InlineKeyboardButton(
                        btn_label,
                        callback_data=f"prompt_review_{order.order_number}"
                    ))
                keyboard.append(row)

        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

        if update.callback_query:
            await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
    finally:
        db.close()
