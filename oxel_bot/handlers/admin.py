import os
import html
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from config import ADMIN_IDS
from database import SessionLocal, User, Product, ProductVariant, Order, OrderStatusHistory, PromoCode, generate_delivery_code
from utils.pdf_invoice import generate_pdf_invoice
from utils.pdf_shipping_label import generate_shipping_label
from services.order_service import get_shipping_label_data, confirm_order_delivery
from utils.vip import get_user_vip_info

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        if update.callback_query:
            await update.callback_query.answer("⛔ Access denied. Admin only.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Access denied. Admin only.")
        return

    db = SessionLocal()
    try:
        total_orders = db.query(Order).count()
        pending_orders = db.query(Order).filter(Order.status == 'pending').count()
        paid_orders = db.query(Order).filter(Order.status == 'paid').count()
        shipped_orders = db.query(Order).filter(Order.status == 'shipped').count()
        delivered_orders = db.query(Order).filter(Order.status == 'delivered').count()
        total_users = db.query(User).count()

        from sqlalchemy import func
        total_revenue = db.query(func.sum(Order.total_price)).filter(
            Order.status.in_(['paid', 'confirmed', 'shipped', 'delivered'])
        ).scalar() or 0

        text = f"""🔐 *ADMIN CONTROL PANEL & STORE MANAGEMENT*
━━━━━━━━━━━━━━━━━━━━
📊 *Store Overview*

👥 Total Registered Users: {total_users}
🛒 Total Orders: {total_orders}
⏳ Pending Verifications: {pending_orders}
✅ Paid/Confirmed Orders: {paid_orders}
🚚 Shipped Orders: {shipped_orders}
🏠 Delivered Orders: {delivered_orders}
💰 Verified Revenue: *{total_revenue:,} ETB*
━━━━━━━━━━━━━━━━━━━━

*⚡ Admin Direct Commands:*
• `/verify ORDER#` — 1-Click Verify & Send PDF
• `/status ORDER# STATUS` — Update order status
• `/ship ORDER# TRACKING` — Mark order as shipped
• `/bulkship ORDER1,ORDER2` — Dispatch multiple
• `/givepoints USER_ID POINTS` — Award points
• `/userinfo USER_ID` — Lookup customer details
• `/broadcast MSG` — Push announcement to all
• `/broadcast_vip MSG` — Push to VIP Gold/Silver
• `/setstock PROD_ID FINISH QTY` — Set inventory"""

        keyboard = [
            [InlineKeyboardButton("⏳ Pending Verifications", callback_data="admin_pending")],
            [InlineKeyboardButton("📊 Export PDF Sales Report", callback_data="export_admin_sales_pdf")],
            [InlineKeyboardButton("📁 Export CSV Data Spreadsheets", callback_data="admin_export_csv_menu")],
            [InlineKeyboardButton("📢 Push Broadcast Engine", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton("🪵 Product CMS & Catalog Editor", callback_data="admin_products")],
            [InlineKeyboardButton("📊 Inventory Stock Levels", callback_data="admin_inventory")],
            [InlineKeyboardButton("🚚 Delivery Route Planner", callback_data="admin_routes")],
            [InlineKeyboardButton("👥 Customer CRM & VIP Directory", callback_data="admin_crm")],
            [InlineKeyboardButton("🎟️ Promo Codes Manager", callback_data="admin_promos")],
            [InlineKeyboardButton("📦 All Orders Log", callback_data="admin_orders")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except Exception:
                try:
                    await update.callback_query.message.delete()
                except Exception:
                    pass
                await update.callback_query.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    finally:
        db.close()


async def admin_export_csv_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    text = (
        "📁 <b>ADMIN CSV DATA EXPORTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Export raw store data to downloadable <code>.csv</code> spreadsheets for Excel &amp; accounting:\n"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Export Orders CSV", callback_data="export_csv_orders")],
        [InlineKeyboardButton("👥 Export Customers CRM CSV", callback_data="export_csv_customers")],
        [InlineKeyboardButton("📦 Export Product Inventory CSV", callback_data="export_csv_inventory")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")]
    ])

    from utils.safe_message import safe_edit_text
    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def check_and_notify_low_stock(bot, product_id: int, finish_name: str):
    """Automated Low-Stock Alert System (Feature 6)."""
    db = SessionLocal()
    try:
        variant = db.query(ProductVariant).filter(
            ProductVariant.product_id == product_id,
            ProductVariant.finish_name == finish_name
        ).first()

        if variant and variant.stock_quantity <= 3:
            product = db.query(Product).filter(Product.id == product_id).first()
            prod_name = product.name if product else f"Product #{product_id}"

            alert_text = f"""🚨 *AUTOMATED LOW STOCK ALERT!*
━━━━━━━━━━━━━━━━━━━━
📦 *Product:* {prod_name}
🪵 *Finish:* {finish_name}
📊 *Remaining Stock:* *{variant.stock_quantity} units left!*

Tap below to instantly add +10 stock:"""

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"⚡ 1-Tap Restock +10 ({finish_name})", callback_data=f"cms_addstock_{variant.id}_10")
            ]])

            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(chat_id=admin_id, text=alert_text, reply_markup=keyboard, parse_mode="Markdown")
                except Exception:
                    pass
    finally:
        db.close()


async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_status: str = 'all'):
    """Full interactive Admin Order Management Log & Filter screen."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        q = db.query(Order)
        if filter_status == 'points_paid':
            q = q.filter(Order.payment_method == 'LOYALTY_POINTS')
        elif filter_status and filter_status != 'all':
            q = q.filter(Order.status == filter_status)

        orders = q.order_by(Order.created_at.desc()).limit(15).all()

        status_emoji = {
            'pending': '⏳', 'paid': '✅', 'verified': '✅',
            'confirmed': '📦', 'shipped': '🚚', 'delivered': '🏠',
            'cancelled': '❌', 'submitted': '⏳'
        }

        filter_labels = {
            'all': '📦 All Orders',
            'pending': '⏳ Pending',
            'verified': '✅ Verified',
            'confirmed': '📦 Confirmed',
            'shipped': '🚚 Shipped',
            'delivered': '🏠 Delivered',
            'cancelled': '❌ Cancelled',
            'points_paid': '🏅 Points Paid',
        }

        label = filter_labels.get(filter_status, filter_status)
        text = f"📦 <b>ADMIN ORDER MANAGEMENT LOG</b>\n━━━━━━━━━━━━━━━━━━━━\nFilter: <b>{html.escape(label)}</b> ({len(orders)} items)\n"
        if not orders:
            text += f"\n<i>No {html.escape(filter_status)} orders found.</i>\n"
        else:
            for o in orders:
                user = db.query(User).filter(User.user_id == o.user_id).first()
                uname = f"@{user.username}" if (user and user.username) else (user.first_name if user else f"User #{o.user_id}")
                emoji = status_emoji.get(o.status, '📌')
                pts_tag = " 🏅" if o.payment_method == 'LOYALTY_POINTS' else ""
                text += f"\n{emoji} <code>{html.escape(o.order_number)}</code> · <b>{o.total_price:,} ETB</b>{pts_tag}\n"
                text += f"   👤 {html.escape(uname)} | Status: <b>{o.status.upper()}</b>\n"
                text += f"   📅 {o.created_at.strftime('%b %d, %Y — %I:%M %p')}\n"

        text += "\n━━━━━━━━━━━━━━━━━━━━\nSelect a filter or tap an order to manage:"

        keyboard = [
            [
                InlineKeyboardButton("All", callback_data="admin_orders_filter_all"),
                InlineKeyboardButton("⏳ Pending", callback_data="admin_orders_filter_pending"),
                InlineKeyboardButton("✅ Confirmed", callback_data="admin_orders_filter_confirmed"),
            ],
            [
                InlineKeyboardButton("🚚 Shipped", callback_data="admin_orders_filter_shipped"),
                InlineKeyboardButton("🏠 Delivered", callback_data="admin_orders_filter_delivered"),
                InlineKeyboardButton("🏅 Points Paid", callback_data="admin_orders_filter_points_paid"),
            ]
        ]

        for o in orders[:8]:
            pts_tag = " 🏅" if o.payment_method == 'LOYALTY_POINTS' else ""
            keyboard.append([
                InlineKeyboardButton(f"⚙️ Manage #{o.order_number} ({o.status.upper()}){pts_tag}", callback_data=f"admin_manage_ord_{o.id}")
            ])

        keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

        if update.callback_query:
            from utils.safe_message import safe_edit_text
            await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        db.close()


async def admin_manage_order(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """Detailed management view for a single order (Verify, Ship, Confirm Delivery, Label, Cancel)."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            await update.callback_query.answer("Order not found!", show_alert=True)
            return

        user = db.query(User).filter(User.user_id == order.user_id).first()
        username = f"@{user.username}" if (user and user.username) else f"ID:{order.user_id}"
        full_name = html.escape(f"{user.first_name or ''} {user.last_name or ''}".strip()) if user else "N/A"
        phone = html.escape(user.phone if (user and user.phone) else "N/A")

        status_emoji = {
            'pending': '⏳', 'submitted': '⏳', 'paid': '✅', 'verified': '✅',
            'confirmed': '📦', 'shipped': '🚚', 'delivered': '🏠', 'cancelled': '❌'
        }
        emoji = status_emoji.get(order.status, '📌')

        items_lines = []
        if order.items:
            for item in order.items:
                eng_str = f" ✍️ <code>{html.escape(item.engraving_text)}</code>" if (item.engraving_text and item.engraving_text.strip()) else ""
                items_lines.append(f"  • {item.quantity}× <b>{html.escape(item.product_name)}</b> ({html.escape(item.finish_variant or 'Standard')}) — {item.subtotal:,} ETB{eng_str}")
        else:
            product = db.query(Product).filter(Product.id == order.product_id).first() if order.product_id else None
            prod_name = html.escape(product.name) if product else 'Item'
            items_lines.append(f"  • {order.quantity or 1}× <b>{prod_name}</b> — {order.total_price:,} ETB")

        items_text = "\n".join(items_lines)
        code_str = f"\n🔐 <b>Delivery Code:</b> <code>{html.escape(order.delivery_code)}</code>" if order.delivery_code else ""
        trk_str = f"\n🚚 <b>Tracking #:</b> <code>{html.escape(order.tracking_number)}</code>" if order.tracking_number else ""
        promo_str = f"\n🎟️ <b>Promo Code:</b> <code>{html.escape(order.promo_code)}</code> (-{order.discount_amount:,} ETB)" if order.promo_code else ""
        shipping_str = f"\n🚚 <b>Delivery Fee:</b> {order.shipping_fee:,} ETB" if order.shipping_fee else ""
        subtotal_str = f"\n🧾 <b>Subtotal:</b> {order.subtotal:,} ETB" if order.subtotal is not None else ""
        pts_tag = " 🏅 <i>Paid with Loyalty Points — auto-confirmed</i>" if order.payment_method == 'LOYALTY_POINTS' else ""
        rating_str = f"\n⭐ <b>Customer Review:</b> {'⭐' * order.review_rating} ({order.review_rating}/5 Stars)" if order.review_rating else ""

        text = (
            f"⚙️ <b>ADMIN ORDER MANAGEMENT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧾 <b>Order #:</b> <code>{html.escape(order.order_number)}</code>{pts_tag}\n"
            f"📌 <b>Status:</b> {emoji} <b>{order.status.upper()}</b>{code_str}{trk_str}\n"
            f"📅 <b>Date:</b> {order.created_at.strftime('%b %d, %Y — %I:%M %p')}\n\n"
            f"👤 <b>Customer:</b> {full_name} ({html.escape(username)})\n"
            f"📞 <b>Phone:</b> {phone}\n"
            f"📍 <b>Address:</b> {html.escape(order.shipping_address or 'N/A')}\n"
            f"🕔 <b>Slot:</b> {html.escape(order.delivery_slot or 'Morning')}\n\n"
            f"📦 <b>Order Items:</b>\n{items_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━{subtotal_str}{shipping_str}{promo_str}\n"
            f"💰 <b>Grand Total:</b> {order.total_price:,} ETB\n"
            f"💳 <b>Payment:</b> {html.escape((order.payment_method or 'N/A').upper())}\n"
            f"📝 <b>Ref:</b> <code>{html.escape(order.payment_reference or 'N/A')}</code>{rating_str}\n\n"
            f"Select an admin action below:"
        )

        keyboard = []

        if order.status in ['pending', 'submitted']:
            keyboard.append([
                InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_order_{order.id}"),
                InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_order_{order.id}")
            ])

        if order.status in ['verified', 'paid', 'confirmed', 'pending']:
            keyboard.append([
                InlineKeyboardButton("🚚 Dispatch / Mark Shipped", callback_data=f"admin_prompt_ship_{order.id}")
            ])

        if order.status == 'shipped':
            keyboard.append([
                InlineKeyboardButton("🔐 Verify Code & Confirm Delivery", callback_data=f"admin_prompt_deliv_code_{order.id}"),
                InlineKeyboardButton("🏠 Mark Delivered Directly", callback_data=f"admin_prompt_deliv_{order.id}")
            ])

        if order.status in ['verified', 'paid', 'confirmed', 'shipped', 'delivered']:
            keyboard.append([
                InlineKeyboardButton("📄 Generate Shipping Label PDF", callback_data=f"admin_gen_label_{order.id}")
            ])

        keyboard.append([
            InlineKeyboardButton("🔙 All Orders", callback_data="admin_orders"),
            InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")
        ])

        from utils.safe_message import safe_edit_text
        await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        db.close()


async def admin_gen_label_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """Generate and send PDF shipping label for order (Confirmed/Paid/Shipped/Delivered ONLY)."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            await update.callback_query.answer("Order not found!", show_alert=True)
            return

        if order.status in ['cancelled', 'rejected', 'pending', 'submitted']:
            await update.callback_query.answer(
                f"⛔ Shipping label cannot be generated for {order.status.upper()} orders!\nOnly confirmed or shipped orders have labels.",
                show_alert=True
            )
            return

        label_data = get_shipping_label_data(db, order.order_number)
        if not label_data:
            await update.callback_query.answer("Label data error.", show_alert=True)
            return

        pdf_path = generate_shipping_label(label_data)
        if os.path.exists(pdf_path):
            await update.callback_query.answer("📄 Generating Shipping Label PDF...", show_alert=False)
            with open(pdf_path, 'rb') as pdf_doc:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=pdf_doc,
                    caption=f"📦 *Shipping Label — Order #{order.order_number}*\nStatus: *{order.status.upper()}*",
                    parse_mode="Markdown"
                )
    finally:
        db.close()


async def admin_prompt_deliv_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """Prompt admin/delivery courier to enter customer's delivery code to confirm delivery."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            await update.callback_query.answer("Order not found!", show_alert=True)
            return

        context.user_data['awaiting_deliv_code_order_id'] = order.id
        await update.callback_query.answer()

        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"admin_manage_ord_{order.id}")]])
        await update.callback_query.edit_message_text(
            f"🔐 *VERIFY DELIVERY CODE — ORDER #{order.order_number}*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Customer: {order.user.first_name if order.user else 'N/A'}\n"
            f"📍 Address: {order.shipping_address or 'N/A'}\n\n"
            f"Please ask the customer for their delivery code and type it below:",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )
    finally:
        db.close()


async def admin_ship_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """1-Click Ship Order from Admin Management screen."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            await update.callback_query.answer("Order not found!", show_alert=True)
            return

        if not order.delivery_code:
            order.delivery_code = generate_delivery_code()

        tracking_num = f"OXEL-TRK-{order.order_number}"
        order.status = 'shipped'
        order.tracking_number = tracking_num
        order.updated_at = datetime.now()
        db.commit()

        # Notify Customer
        try:
            customer_msg = f"""🚚 *YOUR OXEL PACKAGE IS OUT FOR DELIVERY!*
━━━━━━━━━━━━━━━━━━━━
🧾 *Order #:* `{order.order_number}`
📍 *Address:* _{order.shipping_address or 'Addis Ababa'}_
🚚 *Tracking #:* `{tracking_num}`

🔐 *YOUR DELIVERY CONFIRMATION CODE:*
#️⃣ *`{order.delivery_code}`*

⚠️ *INSTRUCTIONS:*
When courier arrives, provide code *`{order.delivery_code}`* to receive your package!"""
            await context.bot.send_message(chat_id=order.user_id, text=customer_msg, parse_mode="Markdown")
        except Exception:
            pass

        await update.callback_query.answer(f"🚚 Order {order.order_number} marked as SHIPPED!", show_alert=True)
        await admin_manage_order(update, context, order_id)
    finally:
        db.close()


async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        orders = db.query(Order).filter(Order.status.in_(['pending', 'submitted'])).order_by(Order.created_at.asc()).all()

        if not orders:
            text = "✅ <b>No pending verifications!</b>\n\nAll payments have been processed."
            keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                )
            return

        header = f"⏳ <b>Pending Verifications: {len(orders)}</b>\n━━━━━━━━━━━━━━━━━━━━\nReview each order below — receipt photo is attached."
        header_keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                header, reply_markup=InlineKeyboardMarkup(header_keyboard), parse_mode="HTML"
            )
            chat_id = update.callback_query.message.chat_id
        else:
            await update.message.reply_text(header, parse_mode="HTML")
            chat_id = update.message.chat_id

        for order in orders:
            user = db.query(User).filter(User.user_id == order.user_id).first()

            username = html.escape(f"@{user.username}" if user and user.username else f"ID:{order.user_id}")
            full_name = html.escape(f"{user.first_name or ''} {user.last_name or ''}".strip()) if user else "N/A"
            phone = html.escape(user.phone if user and user.phone else "N/A")
            promo_line = f"\n🎟️ Promo: <code>{html.escape(order.promo_code)}</code> (-{order.discount_amount:,} ETB)" if order.promo_code else ""
            shipping_line = f"\n🚚 Shipping: <b>{order.shipping_fee:,} ETB</b>" if order.shipping_fee else ""
            slot_line = f"\n🚚 Slot: <i>{html.escape(order.delivery_slot or 'Morning')}</i>"
            date_str = order.created_at.strftime('%b %d, %Y — %I:%M %p')
 
            map_line = ""
            if order.latitude and order.longitude:
                map_line = f'\n🗺️ <a href="https://maps.google.com/?q={order.latitude},{order.longitude}">View on Map</a>'
 
            if order.items:
                items_text = ""
                for item in order.items:
                    engrave_str = f" ✍️ Engrave: <code>{html.escape(item.engraving_text)}</code>" if item.engraving_text else ""
                    items_text += f"   • <b>{html.escape(item.product_name)}</b> — {html.escape(item.finish_variant or 'Standard')} x{item.quantity} · {item.subtotal:,} ETB{engrave_str}\n"
            else:
                product = db.query(Product).filter(Product.id == order.product_id).first()
                items_text = f"   <b>{html.escape(product.name if product else 'N/A')}</b> — {html.escape(order.finish_variant or 'Standard')} x{order.quantity} · {order.total_price:,} ETB\n"
 
            payment_ref = "N/A"
            receipt_file_id = None
            if order.payments:
                latest_payment = order.payments[-1]
                payment_ref = latest_payment.transaction_reference or "N/A"
                receipt_file_id = latest_payment.receipt_file_id
            elif order.payment_reference:
                payment_ref = order.payment_reference
                receipt_file_id = order.receipt_file_id

            caption = (
                f"🔔 <b>PENDING ORDER — VERIFY OR REJECT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🧾 <b>Order #:</b> <code>{html.escape(order.order_number)}</code>\n"
                f"📅 <b>Placed:</b> {date_str}\n\n"
                f"👤 <b>Customer:</b> {full_name} ({username})\n"
                f"📞 <b>Phone:</b> {phone}\n\n"
                f"📦 <b>Items Ordered:</b>\n{items_text}"
                f"   Total: <b>{order.total_price:,} ETB</b>{shipping_line}{promo_line}{slot_line}\n\n"
                f"💳 <b>Payment:</b> {html.escape((order.payment_method or 'N/A').upper())}\n"
                f"   Reference: <code>{html.escape(str(payment_ref))}</code>\n\n"
                f"📍 <b>Delivery Address:</b>\n"
                f"   {html.escape(order.shipping_address or 'Not provided')}{map_line}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

            order_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ Verify {order.order_number}", callback_data=f"verify_order_{order.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_order_{order.id}")
            ]])

            if receipt_file_id:
                try:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=receipt_file_id,
                        caption=caption,
                        reply_markup=order_keyboard,
                        parse_mode="HTML"
                    )
                    continue
                except Exception:
                    logger.warning(f"admin_pending: Could not send receipt photo for order {order.order_number}")

            await context.bot.send_message(
                chat_id=chat_id,
                text=caption + "\n\n⚠️ <i>No receipt screenshot uploaded.</i>",
                reply_markup=order_keyboard,
                parse_mode="HTML"
            )
    finally:
        db.close()



async def verify_order(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("⛔ Admin only!", show_alert=True)
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            await update.callback_query.answer("Order not found!", show_alert=True)
            return

        from services.order_service import update_order_status
        from services.payment_service import verify_payment

        # Verify associated payment if exists (awards loyalty + triggers referral internally)
        if order.payments:
            for payment in order.payments:
                if payment.status == 'submitted':
                    verify_payment(db, payment.id, user_id)
        else:
            # No Payment record: just update order status (legacy flow)
            update_order_status(db, order.id, 'verified', f"Payment verified by admin {user_id}", user_id)

        # Re-fetch order after potential status updates by verify_payment
        db.refresh(order)

        # Trigger Low Stock Alerts if needed
        for item in order.items:
            if item.variant_id:
                await check_and_notify_low_stock(context.bot, item.product_id, item.finish_variant)

        await update.callback_query.answer(
            f"✅ Order {order.order_number} verified & PDF invoice generated!", show_alert=True
        )

        product = db.query(Product).filter(Product.id == order.product_id).first()
        customer = db.query(User).filter(User.user_id == order.user_id).first()

        # Compute loyalty points awarded (1 point per 1 ETB spent)
        points_earned = int(order.total_price)

        # Check if referral reward was triggered for this user
        from database import Referral
        referral = db.query(Referral).filter(
            Referral.referred_user_id == order.user_id,
            Referral.reward_awarded == True
        ).first()
        referrer_notified = referral is not None

        # Build multi-item invoice data
        if order.items:
            invoice_items = [{
                'name': item.product_name,
                'finish': item.finish_variant or 'Standard',
                'engraving': item.engraving_text,
                'quantity': item.quantity,
                'price': item.unit_price,
                'subtotal': item.subtotal
            } for item in order.items]
        else:
            # Legacy single-item fallback
            invoice_items = [{
                'name': product.name if product else "Wooden Accessory",
                'finish': order.finish_variant or "Standard",
                'engraving': order.engraving_text,
                'quantity': order.quantity,
                'price': product.price if product else order.total_price,
                'subtotal': order.total_price
            }]

        invoice_data = {
            'order_number': order.order_number,
            'customer_name': f"{customer.first_name or ''} {customer.last_name or ''}".strip() or "Valued Customer",
            'phone': customer.phone or "N/A",
            'address': order.shipping_address or "Addis Ababa, Ethiopia",
            'items': invoice_items,
            'subtotal': order.subtotal or sum(it['subtotal'] for it in invoice_items),
            'shipping_fee': order.shipping_fee or 0,
            'engraving_fee': order.engraving_fee or 0,
            'total_amount': order.total_price,
            'discount': order.discount_amount or 0,
            'payment_method': order.payment_method or "TELEBIRR/CBE",
            'date': datetime.now().strftime('%b %d, %Y')
        }

        pdf_file_path = generate_pdf_invoice(invoice_data)

        product_display = product.name if product else 'Wooden Accessory'
        finish_display = order.finish_variant or (order.items[0].finish_variant if order.items else '')

        try:
            pname = html.escape(product.name if product else 'Wooden Accessory')
            fdisp = html.escape(finish_display or '')
            addr_disp = html.escape(order.shipping_address or '')
            await context.bot.send_message(
                chat_id=order.user_id,
                text=(
                    f"🎉 <b>PAYMENT VERIFIED — ORDER CONFIRMED!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Your order <code>{html.escape(order.order_number)}</code> for <b>{pname}</b> ({fdisp}) is now being handcrafted!\n\n"
                    f"⏱ Estimated dispatch: <b>1–3 business days</b>\n"
                    f"📍 Shipping to: <i>{addr_disp}</i>\n\n"
                    f"🏅 <b>You earned +{points_earned} Loyalty Points</b> on this order!\n"
                    f"📄 Your official PDF Invoice is attached below."
                ),
                parse_mode="HTML"
            )
            if os.path.exists(pdf_file_path):
                with open(pdf_file_path, 'rb') as doc_file:
                    await context.bot.send_document(
                        chat_id=order.user_id,
                        document=doc_file,
                        caption=f"📄 Official Invoice — Order #{html.escape(order.order_number)}"
                    )

            nudge_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 View & Share My Referral Link", callback_data="loyalty_menu")
            ]])
            await context.bot.send_message(
                chat_id=order.user_id,
                text=(
                    "🤝 <b>REFER FRIENDS &amp; EARN 100 ETB!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Love your new Oxel handcrafted piece? Share the warmth! 🪵\n\n"
                    "<b>Your Referral Benefit:</b>\n"
                    "• You earn <b>+100 Loyalty Points (100 ETB value)</b> every time a friend you referred completes their first order!\n"
                    "• Your friend gets <b>5% WELCOME DISCOUNT</b> on their first purchase — a win-win!\n"
                    "• No limit on referrals!\n\n"
                    "Tap below to get your personal referral link 👇"
                ),
                reply_markup=nudge_keyboard,
                parse_mode="HTML"
            )
        except Exception:
            logger.warning(f"verify_order: Could not send confirmation messages to user {order.user_id} for order {order.order_number}")

        try:
            cname = html.escape(customer.first_name or 'N/A') if customer else 'N/A'
            admin_confirm_text = (
                f"✅ <b>ORDER VERIFIED SUCCESSFULLY</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🧾 Order: <code>{html.escape(order.order_number)}</code>\n"
                f"👤 Customer: {cname} (ID: {order.user_id})\n"
                f"📦 Product: {pname} — {fdisp}\n"
                f"💰 Total: {order.total_price:,} ETB\n"
                f"📍 Ship to: {addr_disp}\n"
                f"🏅 Loyalty Points Awarded: +{points_earned} pts\n"
                f"{'🎁 Referral Bonus Sent to Referrer!' if referrer_notified else ''}\n"
                f"📄 PDF Invoice sent to customer."
            )
            await update.callback_query.message.reply_text(
                admin_confirm_text, parse_mode="HTML"
            )
        except Exception:
            pass

        await admin_pending(update, context)
    finally:
        db.close()


async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return

        from services.payment_service import reject_payment

        # Try to reject via the Payment service (handles stock restoration + audit)
        rejected_via_payment = False
        if order.payments:
            for payment in order.payments:
                if payment.status == 'submitted':
                    reject_payment(db, payment.id, user_id, reason="Payment rejected by admin via Telegram panel")
                    rejected_via_payment = True

        if not rejected_via_payment:
            # Legacy path: no Payment record — update order status directly (restores stock)
            from services.order_service import update_order_status
            update_order_status(db, order.id, 'cancelled', "Payment rejected by admin.", user_id)

        db.refresh(order)
        await update.callback_query.answer(f"❌ Order {order.order_number} rejected & stock restored.", show_alert=True)

        try:
            await context.bot.send_message(
                chat_id=order.user_id,
                text=f"❌ *Payment Unverified*\n\nWe could not verify the payment reference for order `{order.order_number}`.\nPlease contact support @OxelSupport if you believe this is an error.",
                parse_mode="Markdown"
            )
        except Exception:
            logger.warning(f"reject_order: Could not notify user {order.user_id} of rejection for order {order.order_number}")

        await admin_pending(update, context)
    finally:
        db.close()


# ===== FEATURE 2: CUSTOMER MANAGEMENT & CRM =====

async def admin_crm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        users = db.query(User).all()
        text = f"👥 <b>CUSTOMER CRM &amp; VIP DIRECTORY</b> ({len(users)})\n━━━━━━━━━━━━━━━━━━━━\n"

        for u in users:
            vip_info = get_user_vip_info(u.user_id)
            handle = f"@{html.escape(u.username)}" if u.username else "<i>No handle</i>"
            fname = html.escape(u.first_name or 'User')
            lname = html.escape(u.last_name or '')
            fullname = f"{fname} {lname}".strip()
            text += f"\n🆔 <code>{u.user_id}</code> · <b>{fullname}</b> ({handle})\n"
            text += f"   🏅 Tier: <b>{html.escape(vip_info['tier'])}</b> | Points: <code>{u.loyalty_points or 0:,} pts</code>\n"
            text += f"   💰 Total Spend: <b>{vip_info['total_spend']:,} ETB</b>\n"

        text += "\n━━━━━━━━━━━━━━━━━━━━\n💡 <b>Award Points Command:</b> <code>/givepoints USER_ID POINTS</code>\n💡 <b>Lookup User Command:</b> <code>/userinfo USER_ID</code>"

        keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]

        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    finally:
        db.close()


async def givepoints_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/givepoints USER_ID_OR_USERNAME POINTS [reason]`\n\n"
            "Examples:\n"
            "`/givepoints @customer_username 500 Birthday bonus`\n"
            "`/givepoints 123456789 1000 Store credit`",
            parse_mode="Markdown"
        )
        return

    try:
        raw_target = context.args[0].strip()
        pts = int(context.args[1])
        reason = ' '.join(context.args[2:]) if len(context.args) > 2 else "Manual admin award"

        db = SessionLocal()
        try:
            target_user = None

            # 1. Try numerical user_id
            if raw_target.isdigit() or (raw_target.startswith('-') and raw_target[1:].isdigit()):
                target_user = db.query(User).filter(User.user_id == int(raw_target)).first()

            # 2. Try username lookup
            if not target_user:
                clean_uname = raw_target.lstrip('@')
                target_user = db.query(User).filter(User.username.ilike(clean_uname)).first()
                if not target_user:
                    # Create user entry for username if not in DB yet
                    target_user = User(
                        user_id=0,
                        username=clean_uname,
                        first_name=clean_uname,
                        loyalty_points=0
                    )
                    db.add(target_user)
                    db.commit()

            target_user.loyalty_points = max(0, (target_user.loyalty_points or 0) + pts)
            db.commit()

            new_balance = target_user.loyalty_points
            user_lbl = f"@{target_user.username}" if target_user.username else f"ID:{target_user.user_id}"

            await update.message.reply_text(
                f"✅ *Awarded {pts:+} Loyalty Points to {user_lbl}!*\n"
                f"New Balance: *{new_balance:,} pts*\n"
                f"Reason: _{reason}_",
                parse_mode="Markdown"
            )

            # Send notification if numerical Telegram ID exists
            if target_user.user_id and target_user.user_id > 0:
                try:
                    await context.bot.send_message(
                        chat_id=target_user.user_id,
                        text=f"🎁 *BONUS LOYALTY POINTS AWARDED!*\n\nStore Admin awarded you *{pts:+} loyalty points*!\nNew Balance: *{new_balance:,} pts*\nReason: _{reason}_",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
        finally:
            db.close()
    except Exception as e:
        logger.exception(f"givepoints_command: Unexpected error for admin {user_id}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def userinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/userinfo USER_ID`", parse_mode="Markdown")
        return

    try:
        target_id = int(context.args[0])
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == target_id).first()
            if not user:
                await update.message.reply_text(f"❌ User ID <code>{target_id}</code> not found.", parse_mode="HTML")
                return

            orders = db.query(Order).filter(Order.user_id == target_id).all()
            vip_info = get_user_vip_info(target_id)

            fname = html.escape(user.first_name or '')
            lname = html.escape(user.last_name or '')
            fullname = f"{fname} {lname}".strip() or "Customer"
            handle = f"@{html.escape(user.username)}" if user.username else "<i>no handle</i>"

            text = (
                f"👤 <b>CUSTOMER DETAILED PROFILE</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>ID:</b> <code>{user.user_id}</code>\n"
                f"👤 <b>Name:</b> {fullname}\n"
                f"💬 <b>Handle:</b> {handle}\n"
                f"📞 <b>Phone:</b> {html.escape(user.phone or 'N/A')}\n"
                f"🏅 <b>VIP Tier:</b> <b>{html.escape(vip_info['tier'])}</b>\n"
                f"🎁 <b>Loyalty Points:</b> <code>{user.loyalty_points or 0:,} pts</code>\n"
                f"💰 <b>Total Spend:</b> {vip_info['total_spend']:,} ETB\n"
                f"🛒 <b>Total Orders:</b> {len(orders)}\n\n"
                f"📍 <b>Saved Address #1:</b> <i>{html.escape(user.saved_address_1 or 'None')}</i>\n"
                f"📍 <b>Saved Address #2:</b> <i>{html.escape(user.saved_address_2 or 'None')}</i>"
            )

            await update.message.reply_text(text, parse_mode="HTML")
        finally:
            db.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ===== FEATURE 3: ROUTE & DELIVERY SLOT PLANNER =====

async def admin_routes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        orders = db.query(Order).filter(
            Order.status.in_(['paid', 'confirmed', 'shipped'])
        ).order_by(Order.created_at.desc()).all()

        slots = {"Morning": [], "Afternoon": [], "Evening": [], "Unassigned": []}
        for o in orders:
            slot_name = o.delivery_slot or "Morning"
            if "Morning" in slot_name:
                slots["Morning"].append(o)
            elif "Afternoon" in slot_name:
                slots["Afternoon"].append(o)
            elif "Evening" in slot_name:
                slots["Evening"].append(o)
            else:
                slots["Unassigned"].append(o)

        text = f"🚚 *DELIVERY ROUTE & SLOT PLANNER* ({len(orders)})\n━━━━━━━━━━━━━━━━━━━━\n"

        for s_name, o_list in slots.items():
            text += f"\n⏰ *{s_name} Slot ({len(o_list)} deliveries):*\n"
            for o in o_list[:5]:
                product = db.query(Product).filter(Product.id == o.product_id).first()
                p_name = product.name if product else "Item"
                map_str = f" 🗺️" if o.latitude else ""
                text += f"   • `{o.order_number}` — {p_name} | {o.shipping_address or 'N/A'}{map_str}\n"

        text += "\n━━━━━━━━━━━━━━━━━━━━\n💡 *Bulk Dispatch Command:* `/bulkship OXEL-111,OXEL-222`"

        keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]

        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    finally:
        db.close()


async def bulkship_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/bulkship OXEL-111,OXEL-222,OXEL-333`", parse_mode="Markdown")
        return

    raw_nums = ' '.join(context.args)
    order_nums = [n.strip().upper() for n in raw_nums.split(',') if n.strip()]

    db = SessionLocal()
    try:
        shipped_count = 0
        for num in order_nums:
            order = db.query(Order).filter(Order.order_number == num).first()
            if order:
                order.status = 'shipped'
                order.updated_at = datetime.now()
                db.commit()
                shipped_count += 1

                # Send Push Notification
                try:
                    await context.bot.send_message(
                        chat_id=order.user_id,
                        text=f"🚚 *ORDER DISPATCHED!*\n\nYour order `{num}` is out for delivery today!",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

        await update.message.reply_text(
            f"✅ *Bulk Dispatch Complete!*\n\nSuccessfully marked *{shipped_count} orders* as shipped.",
            parse_mode="Markdown"
        )
    finally:
        db.close()


# ===== RICH MEDIA BROADCAST ENGINE =====

async def admin_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        cart_users = len([
            u for u in db.query(User).all()
            if db.execute(
                __import__('sqlalchemy').text(
                    "SELECT COUNT(*) FROM cart_items ci JOIN carts c ON ci.cart_id=c.id WHERE c.user_id=:uid"
                ),
                {"uid": u.user_id}
            ).scalar() > 0
        ])
    finally:
        db.close()

    text = f"""📢 *RICH MEDIA BROADCAST ENGINE*
━━━━━━━━━━━━━━━━━━━━
Reach your customers with *any media type*:
📝 Text & Links · 🖼️ Photos · 🎥 Videos
🎵 Audio · 🎤 Voice · 📄 Files · 🎞️ GIFs

*Select target audience:*

👥 *All Customers* — {total_users} users
👑 *VIP Gold/Silver Only*
🛒 *Abandoned Cart* — ~{cart_users} users with active carts
━━━━━━━━━━━━━━━━━━━━
After choosing audience, simply *send any message* and it will be broadcast."""

    keyboard = [
        [InlineKeyboardButton("👥 Broadcast to All Users", callback_data="bcast_target_all")],
        [InlineKeyboardButton("👑 VIP Gold/Silver Only", callback_data="bcast_target_vip")],
        [InlineKeyboardButton("🛒 Abandoned Cart Users", callback_data="bcast_target_cart")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]

    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def broadcast_set_target(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Stage the broadcast target and prompt admin to send any message."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    context.user_data['bcast_target'] = target
    context.user_data['awaiting_broadcast_msg'] = True

    labels = {
        'all': '👥 All Customers',
        'vip': '👑 VIP Gold/Silver Customers',
        'cart': '🛒 Abandoned Cart Customers',
    }

    text = f"""📢 *BROADCAST STAGING*
━━━━━━━━━━━━━━━━━━━━
📍 *Target:* {labels.get(target, target)}

Now send the message you want to broadcast.
You can send:
  📝 Text (with Markdown, links, etc.)
  🖼️ Photo (with optional caption)
  🎥 Video (with optional caption)
  🎵 Audio / 🎤 Voice note
  📄 Document / File
  🎞️ GIF / Animation
  🗒️ Sticker

I'll show you a preview before sending.

_Send /cancel to abort._"""

    await update.callback_query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast_menu")]]))


async def _do_send_broadcast(context, chat_id: int, staged: dict) -> bool:
    """Send a single staged broadcast message to one chat_id. Returns True on success."""
    try:
        msg_type = staged.get('type')
        caption = staged.get('caption')
        if msg_type == 'text':
            await context.bot.send_message(chat_id=chat_id, text=staged['text'], parse_mode="Markdown",
                                           disable_web_page_preview=False)
        elif msg_type == 'photo':
            await context.bot.send_photo(chat_id=chat_id, photo=staged['file_id'], caption=caption, parse_mode="Markdown")
        elif msg_type == 'video':
            await context.bot.send_video(chat_id=chat_id, video=staged['file_id'], caption=caption, parse_mode="Markdown")
        elif msg_type == 'audio':
            await context.bot.send_audio(chat_id=chat_id, audio=staged['file_id'], caption=caption, parse_mode="Markdown")
        elif msg_type == 'voice':
            await context.bot.send_voice(chat_id=chat_id, voice=staged['file_id'], caption=caption, parse_mode="Markdown")
        elif msg_type == 'document':
            await context.bot.send_document(chat_id=chat_id, document=staged['file_id'], caption=caption, parse_mode="Markdown")
        elif msg_type == 'animation':
            await context.bot.send_animation(chat_id=chat_id, animation=staged['file_id'], caption=caption, parse_mode="Markdown")
        elif msg_type == 'sticker':
            await context.bot.send_sticker(chat_id=chat_id, sticker=staged['file_id'])
        elif msg_type == 'video_note':
            await context.bot.send_video_note(chat_id=chat_id, video_note=staged['file_id'])
        return True
    except Exception:
        return False


async def broadcast_stage_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called from handle_message when admin has sent a broadcast message to stage."""
    msg = update.message
    staged = {}

    if msg.text:
        staged = {'type': 'text', 'text': msg.text}
    elif msg.photo:
        staged = {'type': 'photo', 'file_id': msg.photo[-1].file_id, 'caption': msg.caption}
    elif msg.video:
        staged = {'type': 'video', 'file_id': msg.video.file_id, 'caption': msg.caption}
    elif msg.audio:
        staged = {'type': 'audio', 'file_id': msg.audio.file_id, 'caption': msg.caption}
    elif msg.voice:
        staged = {'type': 'voice', 'file_id': msg.voice.file_id, 'caption': msg.caption}
    elif msg.document:
        staged = {'type': 'document', 'file_id': msg.document.file_id, 'caption': msg.caption}
    elif msg.animation:
        staged = {'type': 'animation', 'file_id': msg.animation.file_id, 'caption': msg.caption}
    elif msg.sticker:
        staged = {'type': 'sticker', 'file_id': msg.sticker.file_id}
    elif msg.video_note:
        staged = {'type': 'video_note', 'file_id': msg.video_note.file_id}
    else:
        await msg.reply_text("❌ Unsupported message type. Please send text, photo, video, audio, voice, file, GIF or sticker.")
        return

    context.user_data['staged_broadcast'] = staged
    context.user_data['awaiting_broadcast_msg'] = False

    target = context.user_data.get('bcast_target', 'all')
    labels = {'all': '👥 All Customers', 'vip': '👑 VIP Gold/Silver', 'cart': '🛒 Abandoned Cart'}

    db = SessionLocal()
    try:
        if target == 'all':
            count = db.query(User).count()
        elif target == 'vip':
            count = sum(1 for u in db.query(User).all() if get_user_vip_info(u.user_id)['tier'] in ['Silver 🥈', 'Gold 🥇'])
        else:
            count = len([
                u for u in db.query(User).all()
                if db.execute(
                    __import__('sqlalchemy').text(
                        "SELECT COUNT(*) FROM cart_items ci JOIN carts c ON ci.cart_id=c.id WHERE c.user_id=:uid"
                    ),
                    {"uid": u.user_id}
                ).scalar() > 0
            ])
    finally:
        db.close()

    type_emoji = {
        'text': '📝', 'photo': '🖼️', 'video': '🎥', 'audio': '🎵',
        'voice': '🎤', 'document': '📄', 'animation': '🎞️', 'sticker': '🗒️', 'video_note': '🎬'
    }
    emoji = type_emoji.get(staged['type'], '📨')

    preview_text = f"""📢 *BROADCAST PREVIEW*
━━━━━━━━━━━━━━━━━━━━
{emoji} *Type:* {staged['type'].replace('_', ' ').title()}
📍 *Target:* {labels.get(target, target)}
👥 *Recipients:* ~{count} users

✅ Ready to send. Confirm or cancel below."""

    keyboard = [
        [InlineKeyboardButton(f"🚀 Send to {count} Users", callback_data="bcast_confirm_send")],
        [InlineKeyboardButton("❌ Cancel Broadcast", callback_data="admin_broadcast_menu")]
    ]

    await msg.reply_text(preview_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def broadcast_confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute the staged broadcast to all target users."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    staged = context.user_data.get('staged_broadcast')
    if not staged:
        await update.callback_query.answer("No broadcast staged!", show_alert=True)
        return

    target = context.user_data.get('bcast_target', 'all')
    await update.callback_query.edit_message_text(
        "⏳ *Sending broadcast...*\n\nPlease wait while we reach all your customers.",
        parse_mode="Markdown"
    )

    db = SessionLocal()
    sent = 0
    failed = 0
    try:
        all_users = db.query(User).all()
        if target == 'vip':
            targets = [u for u in all_users if get_user_vip_info(u.user_id)['tier'] in ['Silver 🥈', 'Gold 🥇']]
        elif target == 'cart':
            targets = [
                u for u in all_users
                if db.execute(
                    __import__('sqlalchemy').text(
                        "SELECT COUNT(*) FROM cart_items ci JOIN carts c ON ci.cart_id=c.id WHERE c.user_id=:uid"
                    ),
                    {"uid": u.user_id}
                ).scalar() > 0
            ]
        else:
            targets = all_users

        for u in targets:
            success = await _do_send_broadcast(context, u.user_id, staged)
            if success:
                sent += 1
            else:
                failed += 1
    finally:
        db.close()

    # Clear staging data
    context.user_data.pop('staged_broadcast', None)
    context.user_data.pop('bcast_target', None)

    labels = {'all': 'All Customers', 'vip': 'VIP Gold/Silver', 'cart': 'Abandoned Cart'}
    type_emoji = {
        'text': '📝', 'photo': '🖼️', 'video': '🎥', 'audio': '🎵',
        'voice': '🎤', 'document': '📄', 'animation': '🎞️', 'sticker': '🗒️', 'video_note': '🎬'
    }
    emoji = type_emoji.get(staged['type'], '📨')

    await update.callback_query.edit_message_text(
        f"""✅ *Broadcast Complete!*
━━━━━━━━━━━━━━━━━━━━
{emoji} Type: {staged['type'].replace('_', ' ').title()}
📍 Segment: {labels.get(target, target)}
✅ Sent: *{sent} users*
❌ Failed/Blocked: {failed} users
━━━━━━━━━━━━━━━━━━━━""",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 New Broadcast", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
        ])
    )

    logger.info(f"Broadcast complete: type={staged['type']}, target={target}, sent={sent}, failed={failed}")


async def broadcast_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy /broadcast_vip — stages a text-only VIP broadcast."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/broadcast_vip Message for VIPs`\n\n💡 Or use the *📢 Broadcast Engine* in Admin Panel for rich media broadcasts.",
            parse_mode="Markdown"
        )
        return

    msg = ' '.join(context.args)
    broadcast_text = f"👑 *EXCLUSIVE VIP ANNOUNCEMENT*\n━━━━━━━━━━━━━━━━━━━━\n\n{msg}"
    staged = {'type': 'text', 'text': broadcast_text}

    db = SessionLocal()
    try:
        users = db.query(User).all()
        sent = 0
        for u in users:
            vip_info = get_user_vip_info(u.user_id)
            if vip_info['tier'] in ['Silver 🥈', 'Gold 🥇']:
                if await _do_send_broadcast(context, u.user_id, staged):
                    sent += 1
        await update.message.reply_text(f"👑 VIP Broadcast sent to *{sent} VIP Gold/Silver customers*.", parse_mode="Markdown")
    finally:
        db.close()


# ===== PRODUCT CMS EDITORS =====

async def admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        products = db.query(Product).all()
        text = f"🪵 *PRODUCT CMS & CATALOG EDITOR* ({len(products)})\n━━━━━━━━━━━━━━━━━━━━\nSelect a product to *edit* or *delete*, or add a new one:\n"

        keyboard = []
        for p in products:
            variants = db.query(ProductVariant).filter(ProductVariant.product_id == p.id).all()
            stock_summary = " / ".join([f"{v.finish_name.split()[-1]}:{v.stock_quantity}" for v in variants])
            text += f"\n🆔 `{p.id}` · *{p.name}* ({p.price:,} ETB)\n"
            text += f"   📂 {p.category} | Stock: {stock_summary}\n"

            keyboard.append([
                InlineKeyboardButton(f"✏️ Edit {p.name}", callback_data=f"cms_edit_{p.id}"),
                InlineKeyboardButton(f"🗑️ Delete", callback_data=f"cms_del_confirm_{p.id}")
            ])

        text += "\n━━━━━━━━━━━━━━━━━━━━"

        keyboard.append([InlineKeyboardButton("➕ Add New Product", callback_data="cms_add_new")])
        keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except Exception:
                try:
                    await update.callback_query.message.delete()
                except Exception:
                    pass
                await update.callback_query.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    finally:
        db.close()


async def cms_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            if update.callback_query:
                await update.callback_query.answer("Product not found!", show_alert=True)
            return

        variants = db.query(ProductVariant).filter(ProductVariant.product_id == product.id).all()

        v_lines = []
        for v in variants:
            badge = "🔴 Out" if v.stock_quantity == 0 else ("🟡 Low" if v.stock_quantity < 4 else "🟢 In Stock")
            size_str = f" | Size: `{v.size_name}`" if v.size_name else ""
            mod_str = f" | Price: `{v.price_modifier:+} ETB`" if v.price_modifier else ""
            img_str = " | 🖼️ Photo Set" if v.image_url else " | 🖼️ Default Photo"
            v_lines.append(f"  • *ID #{v.id}* · {v.finish_name}{size_str}{mod_str}\n    Qty: *{v.stock_quantity} units* [{badge}]{img_str}")

        var_text = "\n".join(v_lines) if v_lines else "  _No variants created yet._"

        text = f"""✏️ *PRODUCT & VARIATION CMS EDITOR: {product.name}*
━━━━━━━━━━━━━━━━━━━━
🆔 *ID:* `{product.id}`
📦 *Name:* {product.name}
💰 *Base Price:* {product.price:,} ETB
📂 *Category:* {product.category}
🖼️ *Default Image:* `{product.image_url or 'Not set'}`
📌 *Status:* {"✅ In Stock" if product.in_stock else "❌ Out of Stock"}

📊 *Variant Stock & Customizations:*
{var_text}

📝 *Description:*
_{product.description}_
━━━━━━━━━━━━━━━━━━━━
Tap a button below to edit product or variant options:"""

        keyboard = [
            [InlineKeyboardButton("💰 Edit Base Price", callback_data=f"cms_setprice_{product.id}"),
             InlineKeyboardButton("🖼️ Edit Default Photo", callback_data=f"cms_setphoto_{product.id}")],
            [InlineKeyboardButton("📝 Edit Description", callback_data=f"cms_setdesc_{product.id}"),
             InlineKeyboardButton("🔄 Toggle In/Out Stock", callback_data=f"cms_togstock_{product.id}")],
            [InlineKeyboardButton("➕ Add New Variant (Finish/Size/Photo)", callback_data=f"cms_addvar_{product.id}")],
        ]

        for v in variants:
            short_lbl = v.finish_name.split()[-1]
            if v.size_name:
                short_lbl += f"-{v.size_name}"
            keyboard.append([
                InlineKeyboardButton(f"🖼️ Photo #{v.id}", callback_data=f"cms_setvphoto_{v.id}"),
                InlineKeyboardButton(f"📐 Size #{v.id}", callback_data=f"cms_setvsize_{v.id}"),
                InlineKeyboardButton(f"💰 Mod #{v.id}", callback_data=f"cms_setvmod_{v.id}"),
                InlineKeyboardButton(f"🔢 Qty #{v.id}", callback_data=f"cms_setvstock_{v.id}"),
            ])

        keyboard.append([
            InlineKeyboardButton("🗑️ DELETE THIS PRODUCT", callback_data=f"cms_del_confirm_{product.id}")
        ])
        keyboard.append([InlineKeyboardButton("🔙 Back to CMS Catalog", callback_data="admin_products")])
        markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    finally:
        db.close()


async def cms_toggle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            product.in_stock = not product.in_stock
            db.commit()
            if product.in_stock:
                from services.alert_service import trigger_restock_notifications
                await trigger_restock_notifications(context.bot, db, product.id)
            await update.callback_query.answer(f"Stock status set to: {'In Stock' if product.in_stock else 'Out of Stock'}", show_alert=True)
            await cms_edit_product(update, context, product_id)
    finally:
        db.close()


async def cms_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE, variant_id: int, amount: int):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
        if variant:
            was_zero = variant.stock_quantity <= 0
            variant.stock_quantity += amount
            db.commit()
            if was_zero and variant.stock_quantity > 0:
                from services.alert_service import trigger_restock_notifications
                await trigger_restock_notifications(context.bot, db, variant.product_id)
            await update.callback_query.answer(f"✅ Added +{amount} stock to {variant.finish_name} (Total: {variant.stock_quantity})", show_alert=True)
            await cms_edit_product(update, context, variant.product_id)
    finally:
        db.close()


async def admin_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        products = db.query(Product).all()
        text = "📊 *Real-Time Inventory Stock Levels*\n━━━━━━━━━━━━━━━━━━━━\n"

        for p in products:
            text += f"\n📦 *{p.name}* (ID: `{p.id}` · Price: {p.price:,} ETB)\n"
            variants = db.query(ProductVariant).filter(ProductVariant.product_id == p.id).all()
            for v in variants:
                badge = "🔴 Out" if v.stock_quantity == 0 else ("🟡 Low" if v.stock_quantity < 4 else "🟢 OK")
                text += f"   • {v.finish_name}: *{v.stock_quantity} units* [{badge}]\n"

        text += "\n💡 *Update stock command:* `/setstock PROD_ID FINISH_NAME QTY`\n_Example: `/setstock 1 Natural Oak 15`_"

        keyboard = [
            [InlineKeyboardButton("🪵 Open Product CMS", callback_data="admin_products")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
        ]

        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    finally:
        db.close()


async def admin_promos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        promos = db.query(PromoCode).all()
        text = f"🎟️ *PROMO CODES MANAGER* ({len(promos)})\n━━━━━━━━━━━━━━━━━━━━\n"

        keyboard = []
        for pr in promos:
            disc_str = f"{pr.discount_percent}% OFF" if (pr.discount_percent and pr.discount_percent > 0) else f"{pr.discount_amount or 0} ETB OFF"
            status_str = "✅ Active" if pr.active else "❌ Inactive"
            uses_str = f"Uses: {pr.current_uses or 0}"
            text += f"\n🎟️ Code: `{pr.code}` — *{disc_str}* [{status_str} · {uses_str}]\n"

            toggle_btn_txt = f"🔴 Deactivate {pr.code}" if pr.active else f"🟢 Activate {pr.code}"
            keyboard.append([
                InlineKeyboardButton(toggle_btn_txt, callback_data=f"cms_togpromo_{pr.id}")
            ])

        text += "\n━━━━━━━━━━━━━━━━━━━━\n💡 *Create Promo Code:* `/addpromo CODE PERCENT`\n_Example: `/addpromo OXEL20 20`_"

        keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])

        from utils.safe_message import safe_edit_text
        await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard))
    finally:
        db.close()


async def cms_toggle_promo(update: Update, context: ContextTypes.DEFAULT_TYPE, promo_id: int):
    """Toggle active/inactive status for a promo code."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
        if promo:
            promo.active = not promo.active
            db.commit()
            status_lbl = "ACTIVE ✅" if promo.active else "INACTIVE ❌"
            await update.callback_query.answer(f"Promo '{promo.code}' → {status_lbl}", show_alert=True)
            await admin_promos(update, context)
    finally:
        db.close()


async def admin_confirm_delivery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """Admin confirms order delivery is complete."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            await update.callback_query.answer("Order not found!", show_alert=True)
            return

        from services.order_service import confirm_order_delivery
        confirm_order_delivery(db, order.order_number, order.delivery_code or '')

        try:
            await context.bot.send_message(
                chat_id=order.user_id,
                text=f"🏠 *ORDER DELIVERED — THANK YOU!*\n\n🧧 *Order #:* `{order.order_number}` has been marked as *DELIVERED*.\n\n⭐ We’d love to hear from you! Tap below to leave a review — it means the world to us. 🙏",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ Leave a Review Now", callback_data=f"prompt_review_{order.order_number}")],
                    [InlineKeyboardButton("📋 My Orders", callback_data="my_orders")]
                ]),
                parse_mode="Markdown"
            )
        except Exception:
            pass

        await update.callback_query.answer(f"🏠 Order {order.order_number} marked DELIVERED!", show_alert=True)
        await admin_manage_order(update, context, order_id)
    finally:
        db.close()


async def admin_promo_wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the inline promo creation wizard."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    context.user_data['promo_wiz_step'] = 'code'
    context.user_data['promo_wiz_data'] = {}

    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_promos")]])
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🏷️ *Create New Promo Code — Wizard (5 steps)*\n━━━━━━━━━━━━━━━━━━━━\n\n*Step 1 — Promo Code Name*\n\nType the promo code (e.g., `VIP20`, `SUMMER15`, `GOLD50`):" ,
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )


async def admin_promo_wizard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle inline button selections during the promo wizard (tier selection + final save)."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    wiz = context.user_data.get('promo_wiz_data', {})
    await update.callback_query.answer()

    if data.startswith('promo_wiz_tier_'):
        tier_key = data.replace('promo_wiz_tier_', '')
        tier_map = {'none': None, 'silver': 'Silver 🥈', 'gold': 'Gold 🥇'}
        wiz['min_loyalty_tier'] = tier_map.get(tier_key)
        context.user_data['promo_wiz_data'] = wiz

        # Show summary and save
        code = wiz.get('code', 'PROMO')
        disc_str = wiz.get('disc_str', '?')
        max_uses = wiz.get('max_uses')
        allowed_ids = wiz.get('allowed_product_ids')
        tier = wiz.get('min_loyalty_tier')

        db = SessionLocal()
        try:
            existing = db.query(PromoCode).filter(PromoCode.code == code).first()
            if existing:
                existing.discount_percent = wiz.get('discount_percent', 0)
                existing.discount_amount = wiz.get('discount_amount', 0)
                existing.max_uses = max_uses
                existing.allowed_product_ids = allowed_ids
                existing.min_loyalty_tier = tier
                existing.active = True
            else:
                promo = PromoCode(
                    code=code,
                    discount_percent=wiz.get('discount_percent', 0),
                    discount_amount=wiz.get('discount_amount', 0),
                    max_uses=max_uses,
                    current_uses=0,
                    per_user_limit=1,
                    allowed_product_ids=allowed_ids,
                    min_loyalty_tier=tier,
                    active=True
                )
                db.add(promo)
            db.commit()
        finally:
            db.close()

        context.user_data.pop('promo_wiz_step', None)
        context.user_data.pop('promo_wiz_data', None)

        summary = (
            f"✅ *Promo Code Created!*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ Code: `{code}` — *{disc_str}*\n"
            f"👤 Max uses: *{max_uses or 'Unlimited'}*\n"
            f"📦 Products: *{allowed_ids or 'All products'}*\n"
            f"🏆 Tier: *{tier or 'All tiers (Bronze+)'}*"
        )
        keyboard = [[InlineKeyboardButton("🏷️ Back to Promo Manager", callback_data="admin_promos")]]
        await update.callback_query.edit_message_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# (admin_orders is defined above — this old duplicate removed)


async def setstock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Access denied.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: `/setstock PRODUCT_ID FINISH_NAME QUANTITY`\nExample: `/setstock 1 Natural Oak 15`",
            parse_mode="Markdown"
        )
        return

    try:
        prod_id = int(context.args[0])
        qty = int(context.args[-1])
        finish = " ".join(context.args[1:-1])

        db = SessionLocal()
        try:
            variant = db.query(ProductVariant).filter(
                ProductVariant.product_id == prod_id,
                ProductVariant.finish_name.ilike(f"%{finish}%")
            ).first()

            if variant:
                variant.stock_quantity = qty
                db.commit()
                await update.message.reply_text(
                    f"✅ *Inventory Stock Updated!*\n\nProduct #{prod_id} ({variant.finish_name}) stock set to: *{qty} units*",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"❌ Variant matching '{finish}' not found for product #{prod_id}.")
        finally:
            db.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def addproduct_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    raw_text = ' '.join(context.args)
    if not raw_text or '|' not in raw_text:
        await update.message.reply_text(
            "Usage: `/addproduct Name | Category | Price | Description`\n\nExample:\n`/addproduct The Apex Stand | Laptop Stand | 2400 | Premium solid hardwood stand`",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in raw_text.split('|')]
    if len(parts) < 4:
        await update.message.reply_text("❌ Please provide: Name | Category | Price | Description")
        return

    name, category, price_str, desc = parts[0], parts[1], parts[2], parts[3]
    try:
        price = int(price_str)
        slug = name.lower().replace(' ', '-')

        db = SessionLocal()
        try:
            product = Product(
                name=name,
                slug=slug,
                category=category,
                price=price,
                description=desc,
                image_url="data/images/the-rise.png",
                in_stock=True
            )
            db.add(product)
            db.commit()
            db.refresh(product)

            for finish in ["Natural Oak", "Dark Walnut", "Midnight Ash"]:
                db.add(ProductVariant(product_id=product.id, finish_name=finish, stock_quantity=10))
            db.commit()

            await update.message.reply_text(
                f"✅ *New Product Added to Store!*\n\n📦 *{name}* (ID: `{product.id}`)\n💰 Price: {price:,} ETB\n📂 Category: {category}",
                parse_mode="Markdown"
            )
        finally:
            db.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Error adding product: {str(e)}")


async def addpromo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create/update promo code.
    Usage: /addpromo CODE PERCENT [max_uses] [product_ids] [tier] [expiry_days]
    Example: /addpromo GOLD20 20 100 1,3 Gold 30
    Or tap ➕ Create in Promo Manager for the step-by-step wizard.
    """
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "🏷️ *Create Promo Code*\n"
            "Usage: `/addpromo CODE PERCENT [max_uses] [product_ids] [tier] [expiry_days]`\n\n"
            "Examples:\n"
            "`/addpromo OXEL20 20` — 20% off, unlimited users\n"
            "`/addpromo VIP20 20 50` — 20% off, max 50 users\n"
            "`/addpromo GOLD20 20 100 1,3 Gold 30` — Gold tier only, products 1&3, 30 day expiry\n\n"
            "_Or tap_ *➕ Create New Promo Code* _in Promo Manager for the guided wizard._",
            parse_mode="Markdown"
        )
        return

    code = context.args[0].upper()
    try:
        percent = int(context.args[1])
        max_uses = int(context.args[2]) if len(context.args) > 2 else None
        allowed_product_ids = context.args[3] if len(context.args) > 3 else None
        tier_arg = context.args[4].lower() if len(context.args) > 4 else None
        expiry_days = int(context.args[5]) if len(context.args) > 5 else None

        tier_map = {'bronze': None, 'silver': 'Silver 🥈', 'gold': 'Gold 🥇', 'none': None}
        min_loyalty_tier = tier_map.get(tier_arg, None) if tier_arg else None

        expiration_date = None
        if expiry_days:
            from datetime import timedelta
            expiration_date = datetime.now() + timedelta(days=expiry_days)

        db = SessionLocal()
        try:
            promo = db.query(PromoCode).filter(PromoCode.code == code).first()
            if promo:
                promo.discount_percent = percent
                promo.max_uses = max_uses
                promo.allowed_product_ids = allowed_product_ids
                promo.min_loyalty_tier = min_loyalty_tier
                promo.expiration_date = expiration_date
                promo.active = True
            else:
                promo = PromoCode(
                    code=code,
                    discount_percent=percent,
                    max_uses=max_uses,
                    current_uses=0,
                    per_user_limit=1,
                    allowed_product_ids=allowed_product_ids,
                    min_loyalty_tier=min_loyalty_tier,
                    expiration_date=expiration_date,
                    active=True
                )
                db.add(promo)
            db.commit()
            details = [
                f"🏷️ Code: `{code}` — *{percent}% OFF*",
                f"👤 Max users: {max_uses or 'Unlimited'}",
                f"📦 Products: {allowed_product_ids or 'All products'}",
                f"🏆 Tier: {min_loyalty_tier or 'All (Bronze+)'}",
                f"📅 Expires: {expiration_date.strftime('%b %d, %Y') if expiration_date else 'Never'}"
            ]
            await update.message.reply_text(
                "✅ *Promo Code Created/Updated!*\n━━━━━━━━━━━━━━━━━━━━\n" + '\n'.join(details),
                parse_mode="Markdown"
            )
        finally:
            db.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/status ORDER_NUMBER STATUS`", parse_mode="Markdown")
        return

    order_number = context.args[0].upper()
    new_status = context.args[1].lower()

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_number == order_number).first()
        if not order:
            await update.message.reply_text(f"❌ Order `{order_number}` not found.", parse_mode="Markdown")
            return

        order.status = new_status
        order.updated_at = datetime.now()
        db.commit()

        status_msg_map = {
            'shipped': f"🚚 *ORDER SHIPPED!*\n\nYour order `{order.order_number}` is on its way!\nTracking: `{order.tracking_number or 'In Transit'}`",
            'delivered': f"🏠 *ORDER DELIVERED!*\n\nYour order `{order.order_number}` has been successfully delivered!\n\nWe hope you love your handcrafted piece. Tap below to rate your item!",
            'confirmed': f"📦 *ORDER CONFIRMED!*\n\nYour order `{order.order_number}` has been confirmed and is being handcrafted."
        }

        if new_status in status_msg_map:
            try:
                keyboard = None
                if new_status == 'delivered':
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("⭐ Rate Your Product (1-5 Stars)", callback_data=f"rate_{order.id}_5")
                    ]])
                await context.bot.send_message(
                    chat_id=order.user_id,
                    text=status_msg_map[new_status],
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        await update.message.reply_text(f"📌 Order `{order_number}` status updated to {new_status.upper()}.", parse_mode="Markdown")
    finally:
        db.close()


async def ship_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/ship ORDER_NUMBER [TRACKING_NUMBER]`", parse_mode="Markdown")
        return

    order_number = context.args[0].upper()
    tracking_number = ' '.join(context.args[1:]) if len(context.args) > 1 else f"OXEL-TRK-{order_number}"

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_number == order_number).first()
        if not order:
            await update.message.reply_text(f"❌ Order `{order_number}` not found.", parse_mode="Markdown")
            return

        if not order.delivery_code:
            order.delivery_code = generate_delivery_code()

        order.status = 'shipped'
        order.tracking_number = tracking_number
        order.updated_at = datetime.now()
        db.commit()

        # Generate Shipping Label PDF for Admin
        label_data = get_shipping_label_data(db, order.id)
        label_pdf_path = generate_shipping_label(label_data)

        # Notify Customer with Delivery Confirmation Code
        try:
            customer_msg = f"""🚚 *YOUR OXEL PACKAGE IS OUT FOR DELIVERY!*
━━━━━━━━━━━━━━━━━━━━
🧾 *Order #:* `{order.order_number}`
📍 *Shipping Address:* _{order.shipping_address or 'Addis Ababa'}_
🚚 *Tracking #:* `{tracking_number}`

🔐 *YOUR DELIVERY CONFIRMATION CODE:*
#️⃣ *`{order.delivery_code}`*

⚠️ *IMPORTANT INSTRUCTIONS:*
When your delivery courier arrives, please give them this 6-digit confirmation code *(`{order.delivery_code}`)* to confirm receipt and claim your package!"""
            await context.bot.send_message(chat_id=order.user_id, text=customer_msg, parse_mode="Markdown")
        except Exception:
            logger.warning(f"ship_command: Could not send delivery code notification to user {order.user_id} for order {order_number}")

        await update.message.reply_text(
            f"🚚 Order `{order_number}` marked as shipped!\n🔐 Customer Delivery Code: `{order.delivery_code}`\n📄 Official Shipping Label generated below:",
            parse_mode="Markdown"
        )
        if os.path.exists(label_pdf_path):
            with open(label_pdf_path, 'rb') as pdf_doc:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=pdf_doc,
                    caption=f"📦 Package Shipping Label — Order #{order_number}"
                )
    finally:
        db.close()


async def shipping_label_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/shipping_label ORDER_NUMBER`", parse_mode="Markdown")
        return

    order_num = context.args[0].upper()
    db = SessionLocal()
    try:
        label_data = get_shipping_label_data(db, order_num)
        if not label_data:
            await update.message.reply_text(f"❌ Order `{order_num}` not found.", parse_mode="Markdown")
            return

        pdf_path = generate_shipping_label(label_data)
        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as pdf_doc:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=pdf_doc,
                    caption=f"📦 Shipping Label — Order #{order_num}\n🔐 Delivery Code: `{label_data['delivery_code']}`",
                    parse_mode="Markdown"
                )
    finally:
        db.close()


async def confirm_delivery_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/confirm_delivery ORDER_NUMBER CONFIRMATION_CODE`\nExample: `/confirm_delivery OXEL-9F3B21 482915`", parse_mode="Markdown")
        return

    order_num = context.args[0].upper()
    code_input = context.args[1].strip()

    db = SessionLocal()
    try:
        success, message, order = confirm_order_delivery(db, order_num, code_input, admin_id=user_id)
        if success:
            await update.message.reply_text(f"✅ *DELIVERY CONFIRMED!*\n\n{message}", parse_mode="Markdown")

            # Notify Customer
            try:
                await context.bot.send_message(
                    chat_id=order.user_id,
                    text=f"""🎉 *PACKAGE DELIVERED & FULFILLED!*
━━━━━━━━━━━━━━━━━━━━
Your order `{order.order_number}` has been successfully received and confirmed via your delivery code.

⭐ We'd love your feedback! Tap below to leave a review anytime.""",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⭐ Leave a Review Now", callback_data=f"prompt_review_{order.order_number}")],
                        [InlineKeyboardButton("📋 My Orders", callback_data="my_orders")]
                    ]),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            await update.message.reply_text(f"⛔ *DELIVERY VERIFICATION FAILED*\n\n{message}", parse_mode="Markdown")
    finally:
        db.close()


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/broadcast Your message here`", parse_mode="Markdown")
        return

    message = ' '.join(context.args)
    broadcast_text = f"📢 *Announcement from Oxel*\n━━━━━━━━━━━━━━━━━━━━\n\n{message}"

    db = SessionLocal()
    try:
        users = db.query(User).all()
        sent = 0
        for u in users:
            try:
                await context.bot.send_message(chat_id=u.user_id, text=broadcast_text, parse_mode="Markdown")
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"📢 Broadcast sent to {sent} users.", parse_mode="Markdown")
    finally:
        db.close()


# ===== FULL CRUD: ADD NEW PRODUCT WIZARD =====

async def cms_add_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the guided Add New Product wizard."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    # Clear any previous wizard state
    context.user_data['new_product'] = {}
    context.user_data['new_product_step'] = 'name'

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_products")]]
    await update.callback_query.edit_message_text(
        """➕ *ADD NEW PRODUCT — Step 1 of 4*
━━━━━━━━━━━━━━━━━━━━
📦 *Product Name*

Type the product name below:
_Example: The Peak — Monitor Stand_""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ===== FULL CRUD: DELETE PRODUCT WITH CONFIRMATION =====

async def cms_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    """Show a hard-confirm screen before deleting a product."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            await update.callback_query.answer("Product not found.", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("🗑️ YES — DELETE PERMANENTLY", callback_data=f"cms_delete_{product_id}")],
            [InlineKeyboardButton("❌ Cancel — Keep Product", callback_data=f"cms_edit_{product_id}")]
        ]
        await update.callback_query.edit_message_text(
            f"""⚠️ *CONFIRM PRODUCT DELETION*
━━━━━━━━━━━━━━━━━━━━
You are about to permanently delete:

📦 *{product.name}* (ID: `{product.id}`)
💰 Price: {product.price:,} ETB
📂 Category: {product.category}

❗ This will also delete all its variants and stock records.
*This action CANNOT be undone.*

Are you sure?""",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    finally:
        db.close()


async def cms_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    """Permanently delete a product and all its variants."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            await update.callback_query.answer("Product not found.", show_alert=True)
            return

        name = product.name
        # Delete variants first (foreign key)
        db.query(ProductVariant).filter(ProductVariant.product_id == product_id).delete()
        db.delete(product)
        db.commit()

        await update.callback_query.answer(f"🗑️ '{name}' deleted.", show_alert=True)
        await admin_products(update, context)
    finally:
        db.close()
