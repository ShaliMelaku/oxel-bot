import os
import html
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS, TELEBIRR_NUMBER, CBE_NUMBER
from database import SessionLocal, User
from utils.keyboards import main_menu_keyboard
from utils.safe_message import safe_edit_text
from services.order_service import create_order_from_cart
from services.payment_service import create_payment
from services.cart_service import get_cart_summary, clear_cart

logger = logging.getLogger(__name__)


def format_address_html(address: str, lat: float = None, lon: float = None) -> str:
    """Format address for HTML telegram messages with clickable Google Maps links."""
    if lat and lon:
        return f"<a href='https://maps.google.com/?q={lat:.6f},{lon:.6f}'>🗺️ Open in Google Maps</a>"
    if address and "https://maps.google.com" in address:
        import re
        match = re.search(r'(https://maps\.google\.com/\S+)', address)
        if match:
            url = match.group(1)
            return f"<a href='{url}'>🗺️ Open in Google Maps</a>"
    return html.escape(address or "N/A")


async def payment_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    """Show payment details for selected payment method."""
    query = update.callback_query
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        summary = get_cart_summary(db, user_id)
        if not summary['items']:
            await query.answer("Your cart is empty!", show_alert=True)
            return

        promo_code = context.user_data.get('applied_promo')
        discount = context.user_data.get('discount_amount', 0)
        total = max(0, summary['subtotal'] - discount)
        context.user_data['cart_total'] = total

        if method == 'telebirr':
            number = TELEBIRR_NUMBER
            name = "Telebirr"
            emoji = "💳"
        else:
            number = CBE_NUMBER
            name = "CBE Mobile"
            emoji = "🏦"

        context.user_data['payment_method'] = method
        discount_line = f"\n🎟️ <b>Discount Applied:</b> -{discount:,} ETB" if discount > 0 else ""

        text = (
            f"{emoji} <b>{html.escape(name)} Payment Instructions</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{discount_line}\n"
            f"💰 <b>Send Exactly:</b> <code>{total:,} ETB</code>\n"
            f"📱 <b>To Account/Number:</b> <code>{html.escape(str(number))}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Important Steps:</b>\n"
            f"1️⃣ Use your full name as the transfer reference\n"
            f"2️⃣ Send the <b>exact</b> amount shown above ({total:,} ETB)\n"
            f"3️⃣ Take a clear screenshot of your payment confirmation\n"
            f"4️⃣ Tap '📸 Upload Receipt' below to attach your screenshot\n\n"
            f"⚠️ <b>Note:</b> Manual payment verification takes 2–24 hours."
        )

        keyboard = [
            [InlineKeyboardButton("📸 Upload Receipt", callback_data="upload_receipt")],
            [InlineKeyboardButton("🔙 Change Payment Method", callback_data="confirm_address")]
        ]

        await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    finally:
        db.close()


async def upload_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Payment Methods", callback_data="confirm_address")],
        [InlineKeyboardButton("🛒 Back to Cart", callback_data="view_cart")]
    ])
    await safe_edit_text(
        update, context,
        "📸 <b>Upload Payment Receipt</b>\n\nPlease send a <b>screenshot</b> or photo of your payment confirmation now.\n\n<i>Accepted: screenshot, photo, PDF</i>",
        keyboard,
        parse_mode="HTML"
    )
    context.user_data['awaiting_receipt'] = True


async def process_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data['receipt_file_id'] = photo.file_id
    context.user_data['awaiting_receipt'] = False

    await update.message.reply_text(
        "✅ <b>Receipt screenshot received!</b>\n\nPlease type your <b>payment transaction reference number</b> below:",
        parse_mode="HTML"
    )
    context.user_data['awaiting_reference'] = True


async def process_reference(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import re
    raw_input = update.message.text.strip()
    payment_method = str(context.user_data.get('payment_method', 'telebirr')).lower()
    extracted_ref = None

    if 'telebirr' in payment_method:
        # 1. Try extracting from full SMS message format: "transaction number is DE84OYCUWM"
        m1 = re.search(r'transaction\s+number\s+is\s+([A-Za-z0-9]+)', raw_input, re.IGNORECASE)
        if m1:
            extracted_ref = m1.group(1).upper()
        else:
            # 2. Try extracting from Telebirr receipt URL: "/receipt/DE84OYCUWM"
            m2 = re.search(r'receipt/([A-Za-z0-9]+)', raw_input, re.IGNORECASE)
            if m2:
                extracted_ref = m2.group(1).upper()
            else:
                # 3. Direct alphanumeric code check (6–20 characters, e.g. DE84OYCUWM or 12345678)
                m3 = re.search(r'\b[A-Za-z0-9]{6,20}\b', raw_input)
                if m3 and len(raw_input) < 30:
                    extracted_ref = raw_input.upper()

        if not extracted_ref:
            await update.message.reply_text(
                "❌ <b>Invalid TeleBirr Reference or Message</b>\n\n"
                "You can paste your full Telebirr SMS confirmation, or type your transaction code (e.g., <code>DE84OYCUWM</code>).\n\n"
                "Please paste your message or enter your reference number:",
                parse_mode="HTML"
            )
            return

    elif 'cbe' in payment_method:
        # 1. Try extracting from CBE receipt URL: "Mbreciept.cbe.com.et/FT26128BTCZH-70943188"
        m1 = re.search(r'Mbreciept\.cbe\.com\.et/([A-Za-z0-9\-]+)', raw_input, re.IGNORECASE)
        if m1:
            extracted_ref = m1.group(1).upper()
        else:
            # 2. Try extracting FT transaction code (e.g. FT26128BTCZH)
            m2 = re.search(r'\b(FT[A-Za-z0-9\-]+)\b', raw_input, re.IGNORECASE)
            if m2:
                extracted_ref = m2.group(1).upper()
            else:
                # 3. Direct alphanumeric code check (6–35 characters)
                if len(raw_input) < 40 and re.match(r'^[A-Za-z0-9\-]{6,35}$', raw_input):
                    extracted_ref = raw_input.upper()

        if not extracted_ref:
            await update.message.reply_text(
                "❌ <b>Invalid CBE Reference or Message</b>\n\n"
                "You can paste your full CBE SMS notification, or type your transaction code (e.g., <code>FT26128BTCZH</code>).\n\n"
                "Please paste your message or enter your reference number:",
                parse_mode="HTML"
            )
            return
    else:
        extracted_ref = raw_input[:50]

    context.user_data['payment_reference'] = extracted_ref
    context.user_data['raw_payment_sms'] = raw_input
    context.user_data['awaiting_reference'] = False

    cart_total = context.user_data.get('cart_total', 0)
    phone = context.user_data.get('shipping_phone', 'Not set')
    address = context.user_data.get('shipping_address', 'Not set')

    preview_text = (
        f"📋 <b>PLEASE CONFIRM YOUR PAYMENT DETAILS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <b>Payment Method:</b> {payment_method.upper()}\n"
        f"🔢 <b>Extracted Ref Code:</b> <code>{html.escape(extracted_ref)}</code>\n"
        f"💰 <b>Amount Due:</b> {cart_total:,} ETB\n"
        f"📞 <b>Contact Phone:</b> <code>{html.escape(phone)}</code>\n"
        f"📍 <b>Delivery Address:</b> {html.escape(address)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<i>Please verify your payment information above. Tap <b>Confirm &amp; Submit Order</b> to submit your order to our team for verification.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Submit Order", callback_data="confirm_submit_order")],
        [InlineKeyboardButton("✏️ Re-enter Payment Info", callback_data="reenter_payment_info")]
    ])

    await update.message.reply_text(
        preview_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def reenter_payment_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow customer to re-enter their payment transaction info."""
    query = update.callback_query
    method = context.user_data.get('payment_method', 'telebirr')
    context.user_data['awaiting_reference'] = True

    await safe_edit_text(
        update, context,
        f"✏️ <b>Re-enter Payment Information ({method.upper()})</b>\n\n"
        f"Please paste your full SMS notification or type your transaction reference code below:",
        parse_mode="HTML"
    )


async def place_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Place multi-item order via Order & Payment services."""
    user_id = update.effective_user.id
    address = context.user_data.get('shipping_address', '')
    payment_method = context.user_data.get('payment_method', 'telebirr')
    reference = context.user_data.get('payment_reference', '')
    receipt_file_id = context.user_data.get('receipt_file_id', '')
    promo_code = context.user_data.get('applied_promo', '')
    delivery_slot = context.user_data.get('delivery_slot', 'Morning (9 AM – 12 PM)')
    lat = context.user_data.get('location_lat')
    lon = context.user_data.get('location_lon')

    db = SessionLocal()
    try:
        from models.user import sync_telegram_user
        user = sync_telegram_user(db, update.effective_user)

        # Create multi-item order using Order Service
        phone = context.user_data.get('shipping_phone')
        try:
            order = create_order_from_cart(
                db,
                user_id=user_id,
                payment_method=payment_method,
                shipping_address=address,
                delivery_slot=delivery_slot,
                phone=phone,
                promo_code=promo_code,
                latitude=lat,
                longitude=lon
            )
        except ValueError as ve:
            await update.message.reply_text(f"⚠️ *Checkout Notice:* {str(ve)}", parse_mode="Markdown")
            return

        # Create Payment record using Payment Service
        payment = create_payment(
            db,
            order_id=order.id,
            payment_method=payment_method,
            amount=order.total_price,
            transaction_reference=reference,
            receipt_file_id=receipt_file_id
        )

        db.refresh(user)
        current_points = user.loyalty_points or 0

        # Clear session
        for key in ['cart', 'cart_total', 'shipping_address', 'payment_method',
                    'payment_reference', 'receipt_file_id', 'discount_amount',
                    'applied_promo', 'location_lat', 'location_lon']:
            context.user_data.pop(key, None)

        itemized_lines = [
            f"  • {item.quantity}× <b>{html.escape(item.product_name)}</b> ({html.escape(item.finish_variant or 'Standard')}) — {item.subtotal:,} ETB"
            for item in order.items
        ]
        itemized_str = "\n".join(itemized_lines)

        discount_line = f"\n🎟️ <b>Discount Applied:</b> -{order.discount_amount:,} ETB" if order.discount_amount > 0 else ""

        confirmation = (
            f"🎉 <b>ORDER PLACED SUCCESSFULLY!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Order Number:</b> <code>{html.escape(order.order_number)}</code>\n\n"
            f"📦 <b>Itemized Summary:</b>\n{itemized_str}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━{discount_line}\n"
            f"💰 <b>Grand Total:</b> {order.total_price:,} ETB\n"
            f"💳 <b>Payment Method:</b> {html.escape(payment_method.upper())}\n"
            f"📝 <b>Transaction Ref:</b> <code>{html.escape(reference or 'N/A')}</code>\n"
            f"📍 <b>Shipping Address:</b> {html.escape(address)}\n"
            f"📌 <b>Status:</b> ⏳ Pending Verification\n"
            f"🏅 <b>Current Loyalty Points:</b> {current_points:,} pts\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Next Steps:</b>\n"
            f"1️⃣ Our team will verify your payment (2–24h)\n"
            f"2️⃣ You'll receive status notifications\n"
            f"3️⃣ Track your order anytime below\n\n"
            f"Thank you for choosing Oxel! 🪵✨"
        )

        keyboard = [
            [InlineKeyboardButton("🔍 Track Order", callback_data=f"refresh_order_{order.order_number}")],
            [InlineKeyboardButton("🏅 My Loyalty Points", callback_data="loyalty_menu")],
            [InlineKeyboardButton("📋 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📦 Browse More", callback_data="catalog"),
             InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]

        success_banner_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'data', 'images', 'order_success_banner.png')
        )

        target_msg = update.callback_query.message if update.callback_query else update.message
        if update.callback_query:
            try:
                await update.callback_query.answer("Order submitted successfully!")
            except Exception:
                pass

        if os.path.exists(success_banner_path):
            with open(success_banner_path, 'rb') as banner_file:
                await target_msg.reply_photo(
                    photo=banner_file,
                    caption=confirmation,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
        else:
            await target_msg.reply_text(
                confirmation,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

        # Notify store admins
        raw_sms = context.user_data.get('raw_payment_sms')
        sms_line = f"\n💬 <b>Shared SMS Details:</b>\n<i>{html.escape(raw_sms)}</i>\n" if raw_sms else "\n"

        admin_items = "\n".join([
            f"  • {item.quantity}× {html.escape(item.product_name)} ({html.escape(item.finish_variant or 'Standard')})"
            for item in order.items
        ])
        cust_name = html.escape(update.effective_user.first_name or '')
        cust_handle = html.escape(update.effective_user.username or 'N/A')
        addr_display = format_address_html(address, lat, lon)
        admin_text = (
            f"🔔 <b>NEW ORDER RECEIVED!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Customer: {cust_name} (@{cust_handle})\n"
            f"🆔 Telegram ID: <code>{user_id}</code>\n"
            f"📞 Contact Phone: <code>{html.escape(order.phone or phone or 'N/A')}</code>\n"
            f"🔢 Order Number: <code>{html.escape(order.order_number)}</code>\n"
            f"📦 Items:\n{admin_items}\n"
            f"💰 Total: {order.total_price:,} ETB\n"
            f"💳 Payment: {html.escape(payment_method.upper())}\n"
            f"📝 Ref / Code: <code>{html.escape(reference or 'N/A')}</code>{sms_line}"
            f"📍 Address / GPS: {addr_display}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        admin_keyboard = [[
            InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_pay_{payment.id}"),
            InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_pay_{payment.id}")
        ]]

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    reply_markup=InlineKeyboardMarkup(admin_keyboard),
                    parse_mode="HTML"
                )
                if receipt_file_id:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=receipt_file_id,
                        caption=f"📸 Payment Receipt for Order #{html.escape(order.order_number)}"
                    )
            except Exception:
                logger.exception(f"Failed sending admin notification to {admin_id}")

    except Exception:
        logger.exception("Error placing multi-item order")
        await update.message.reply_text(
            "❌ <b>Error placing order</b>\n\nPlease try again or contact support.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
    finally:
        db.close()


async def pay_with_points_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Pay with Loyalty Points option cleanly."""
    query = update.callback_query
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        from utils.vip import sync_user_loyalty_and_vip
        vdata = sync_user_loyalty_and_vip(db, user_id)
        pts = vdata.get('points', 0)

        summary = get_cart_summary(db, user_id)
        if not summary['items']:
            try:
                await query.answer("Your cart is empty!", show_alert=True)
            except Exception:
                pass
            return

        promo_code = context.user_data.get('applied_promo')
        discount = context.user_data.get('discount_amount', 0)
        subtotal = summary['subtotal']
        total = max(0, subtotal - discount)

        if pts <= 0:
            try:
                await query.answer("⚠️ You have 0 loyalty points. Please select Telebirr or CBE.", show_alert=True)
            except Exception:
                pass
            return

        address = context.user_data.get('shipping_address') or "Addis Ababa, Ethiopia"
        delivery_slot = context.user_data.get('delivery_slot') or "Morning (9 AM – 12 PM)"
        lat = context.user_data.get('location_lat')
        lon = context.user_data.get('location_lon')

        if pts >= total:
            # 100% Paid by Loyalty Points!
            from models.user import sync_telegram_user
            user = sync_telegram_user(db, update.effective_user)
            if user:
                user.loyalty_points = max(0, pts - total)
                db.commit()

            context.user_data['payment_method'] = 'LOYALTY_POINTS'
            context.user_data['payment_reference'] = f"PTS-PAID-{user_id}"

            # Create Order directly with confirmed status
            phone = context.user_data.get('shipping_phone')
            order = create_order_from_cart(
                db,
                user_id=user_id,
                payment_method='LOYALTY_POINTS',
                shipping_address=address,
                delivery_slot=delivery_slot,
                phone=phone,
                promo_code=promo_code,
                latitude=lat,
                longitude=lon
            )

            order.status = 'submitted'
            order.payment_reference = f"PTS-PAID-{order.id}"
            db.commit()

            # Create Payment record with submitted status (so it shows in Pending Verifications)
            payment = create_payment(
                db,
                order_id=order.id,
                payment_method='LOYALTY_POINTS',
                amount=total,
                transaction_reference=f"PTS-PAID-{order.id}"
            )
            payment.status = 'submitted'
            db.commit()

            clear_cart(db, user_id)

            itemized_lines = [
                f"  • {item.quantity}× <b>{html.escape(item.product_name)}</b> ({html.escape(item.finish_variant or 'Standard')}) — {item.subtotal:,} ETB"
                for item in order.items
            ]
            itemized_str = "\n".join(itemized_lines)
            discount_line = f"\n🎟️ <b>Promo Discount:</b> -{order.discount_amount:,} ETB" if order.discount_amount > 0 else ""

            msg_text = (
                f"🎉 <b>ORDER SUBMITTED &amp; PAID VIA LOYALTY POINTS!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🧾 <b>Order Number:</b> <code>{html.escape(order.order_number)}</code>\n\n"
                f"📦 <b>Itemized Summary:</b>\n{itemized_str}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━{discount_line}\n"
                f"💰 <b>Grand Total:</b> {total:,} ETB (Paid in full with {total:,} pts)\n"
                f"🏅 <b>Remaining Points Balance:</b> <code>{(pts - total):,} pts</code>\n"
                f"🚚 <b>Delivery Slot:</b> {html.escape(delivery_slot)}\n"
                f"📍 <b>Shipping Address:</b> {html.escape(address)}\n"
                f"📌 <b>Status:</b> ⏳ Pending Verification\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Thank you for choosing Oxel! 🪵✨\n"
                f"Your order has been submitted and is pending verification."
            )

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Track Order", callback_data=f"refresh_order_{order.order_number}")],
                [InlineKeyboardButton("📦 My Orders Log", callback_data="my_orders")],
                [InlineKeyboardButton("🏅 My Loyalty Points", callback_data="loyalty_menu")],
                [InlineKeyboardButton("📦 Browse More", callback_data="catalog"),
                 InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ])

            success_banner_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', 'data', 'images', 'order_success_banner.png')
            )

            # Cleanly send success message (with photo banner if exists)
            try:
                await query.message.delete()
            except Exception:
                pass

            if os.path.exists(success_banner_path):
                with open(success_banner_path, 'rb') as banner_file:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=banner_file,
                        caption=msg_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=msg_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )

            # Notify admins with action buttons for Pending Verification
            pts_cust_name = html.escape(update.effective_user.first_name or '')
            pts_cust_handle = html.escape(update.effective_user.username or 'N/A')
            admin_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_pay_{payment.id}"),
                InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_pay_{payment.id}")
            ]])
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"🔔 <b>NEW ORDER — PAID 100% VIA LOYALTY POINTS</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🧾 Order #: <code>{html.escape(order.order_number)}</code>\n"
                            f"👤 Customer: {pts_cust_name} (@{pts_cust_handle})\n"
                            f"📞 Phone: <code>{html.escape(order.phone or phone or 'N/A')}</code>\n"
                            f"💰 Total: {total:,} ETB ({total:,} points redeemed)\n"
                            f"📌 Status: ⏳ Pending Verification"
                        ),
                        reply_markup=admin_keyboard,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        else:
            # Partial Points Payment: deduct all available points as discount
            user = db.query(User).filter(User.user_id == user_id).first()
            applied_pts = pts
            if user:
                user.loyalty_points = 0
                db.commit()

            new_discount = discount + applied_pts
            new_total = max(0, subtotal - new_discount)

            context.user_data['discount_amount'] = new_discount
            context.user_data['cart_total'] = new_total

            # Show updated payment instructions for remaining balance
            text = (
                f"🏅 <b>Loyalty Points Applied!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎟️ <b>Points Applied:</b> -{applied_pts:,} ETB\n"
                f"💰 <b>Remaining Amount Due:</b> <code>{new_total:,} ETB</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Select payment method for remaining balance:"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Pay Remaining via Telebirr", callback_data="pay_telebirr")],
                [InlineKeyboardButton("🏦 Pay Remaining via CBE Mobile", callback_data="pay_cbe")],
                [InlineKeyboardButton("🛒 Back to Cart", callback_data="view_cart")]
            ])
            await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")

    except Exception as e:
        logger.exception("Error processing pay_with_points_handler")
        try:
            await query.message.reply_text(
                f"⚠️ <b>Checkout Notice:</b> {html.escape(str(e))}\n\nPlease try checking out again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 View Cart", callback_data="view_cart")]]),
                parse_mode="HTML"
            )
        except Exception:
            pass
    finally:
        db.close()
