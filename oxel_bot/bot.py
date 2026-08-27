import logging
import sys
import os
import html

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from config import BOT_TOKEN, ADMIN_IDS
from database import create_tables, seed_products, SessionLocal, PromoCode, User, Product, ProductVariant
from handlers.start import start_command, help_command, about_command
from handlers.catalog import catalog_command, show_category, show_product_detail
from handlers.cart import (
    add_to_cart,
    view_cart,
    prompt_clear_cart,
    clear_cart,
    clear_cart_command,
    update_cart_handler,
    adjust_quantity
)
from handlers.checkout import checkout, process_address, process_phone, confirm_address
from handlers.payment import (
    payment_instructions, upload_receipt, process_receipt,
    process_reference, place_order, pay_with_points_handler, reenter_payment_info_handler
)
from handlers.tracking import track_order, process_tracking, show_order_status, my_orders
from handlers.admin import (
    admin_panel, admin_orders, admin_manage_order, admin_gen_label_callback, admin_ship_order_callback,
    admin_pending, admin_inventory, admin_products, admin_promos, cms_toggle_promo, admin_crm, admin_routes,
    admin_broadcast_menu, broadcast_set_target, broadcast_stage_message, broadcast_confirm_send,
    cms_add_new_product, cms_confirm_delete, cms_delete_product,
    verify_order, reject_order,
    status_command, ship_command, broadcast_command, setstock_command,
    addproduct_command, addpromo_command, cms_edit_product, cms_toggle_stock, cms_add_stock,
    givepoints_command, userinfo_command, bulkship_command, broadcast_vip_command,
    shipping_label_command, confirm_delivery_command,
    admin_confirm_delivery_callback, admin_promo_wizard_start, admin_promo_wizard_callback,
    admin_prompt_deliv_code_callback
)
from handlers.loyalty import loyalty_menu, redeem_points_for_discount
from handlers.profile import user_profile_menu
from handlers.reviews import prompt_order_rating, process_rating
from handlers.bundle import (
    show_bundle_detail, bundle_start_wizard, bundle_color_step,
    bundle_back_step, bundle_confirm, bundle_add_to_cart
)
from utils.keyboards import main_menu_keyboard
from utils.safe_message import safe_edit_text
from services.cart_service import get_cart_summary
from services.promo_service import validate_promo_code

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== CALLBACK ROUTER =====

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Always sync live Telegram user information (handle and names) to DB
    if update.effective_user:
        db = SessionLocal()
        try:
            from models.user import sync_telegram_user
            sync_telegram_user(db, update.effective_user)
        except Exception:
            pass
        finally:
            db.close()

    # Main navigation
    if data == 'main_menu':
        await start_command(update, context)
    elif data == 'catalog':
        await catalog_command(update, context)
    elif data == 'view_cart':
        await view_cart(update, context)
    elif data == 'clear_cart':
        await prompt_clear_cart(update, context)
    elif data == 'confirm_clear_cart':
        await clear_cart(update, context)
    elif data == 'update_cart':
        await update_cart_handler(update, context)
    elif data == 'track_order':
        await track_order(update, context)
    elif data == 'my_orders':
        await my_orders(update, context)
    elif data == 'help':
        await help_command(update, context)
    elif data == 'about':
        await about_command(update, context)
    elif data == 'loyalty_menu':
        await loyalty_menu(update, context)
    elif data == 'redeem_points':
        user_id = update.effective_user.id
        discount = redeem_points_for_discount(user_id)
        if discount > 0:
            context.user_data['applied_promo'] = 'LOYALTY_POINTS'
            context.user_data['discount_amount'] = discount
            await query.answer(f"🎉 {discount:,} ETB redeemed from your loyalty points!", show_alert=True)
        else:
            await query.answer("No redeemable points available.", show_alert=True)
        await view_cart(update, context)
    elif data == 'contact_support':
        from config import TELEGRAM_CHANNEL, INSTAGRAM_URL, TIKTOK_URL, SHOP_WEBSITE
        contact_text = (
            "<b>📞 Contact Support</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Our team will respond within 24 hours.\n\n"
            f"📢 Telegram: {TELEGRAM_CHANNEL}\n"
            f"📸 Instagram: {INSTAGRAM_URL}\n"
            f"🎵 TikTok: {TIKTOK_URL}\n"
            "📧 Contact us via Telegram for support\n\n"
            "🕐 Mon–Fri: 9:00 AM – 6:00 PM EAT"
        )
        await safe_edit_text(
            update, context,
            contact_text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

    elif data == 'user_profile':
        await user_profile_menu(update, context)
    elif data.startswith('slot_'):
        slot_map = {
            'slot_morning': '🌅 Morning (9 AM – 12 PM)',
            'slot_afternoon': '☀️ Afternoon (2 PM – 5 PM)',
            'slot_evening': '🌙 Evening (5 PM – 8 PM)'
        }
        context.user_data['delivery_slot'] = slot_map.get(data, 'Morning (9 AM – 12 PM)')
        await confirm_address(update, context)
    elif data.startswith('prompt_review_') or data.startswith('review_order_'):
        ord_num = data.replace('prompt_review_', '').replace('review_order_', '')
        await prompt_order_rating(update, context, ord_num)
    elif data.startswith('rate_'):
        parts = data.split('_')
        order_id = int(parts[1])
        rating = int(parts[2])
        await process_rating(update, context, order_id, rating)
    elif data == 'edit_saved_addr_1':
        await safe_edit_text(update, context, "✏️ *Edit Primary Address #1*\n\nPlease type your primary shipping address:")
        context.user_data['awaiting_addr1'] = True
    elif data == 'edit_saved_addr_2':
        await safe_edit_text(update, context, "✏️ *Edit Secondary Address #2*\n\nPlease type your secondary shipping address:")
        context.user_data['awaiting_addr2'] = True
    elif data == 'checkout':
        await checkout(update, context)
    elif data == 'confirm_address':
        await confirm_address(update, context)
    elif data == 'edit_address':
        await safe_edit_text(
            update, context,
            "✏️ *Re-enter Address*\n\nPlease type your shipping address:\n_Format: City, Sub-city, Phone Number_"
        )
        context.user_data['awaiting_address'] = True
    elif data == 'apply_promo':
        from utils.keyboards import promo_input_reply_keyboard
        await safe_edit_text(
            update, context,
            "🎟️ <b>Apply Promo Code</b>\n\nTap a quick code on your keyboard below, or type your custom promo code:",
            parse_mode="HTML"
        )
        await query.message.reply_text(
            "👇 Quick promo options available on your keyboard:",
            reply_markup=promo_input_reply_keyboard()
        )
        context.user_data['awaiting_promo'] = True
    elif data == 'upload_receipt':
        await upload_receipt(update, context)

    # Payment methods & confirmation
    elif data == 'pay_telebirr':
        await payment_instructions(update, context, 'telebirr')
    elif data == 'pay_cbe':
        await payment_instructions(update, context, 'cbe')
    elif data == 'pay_points':
        await pay_with_points_handler(update, context)
    elif data == 'confirm_submit_order':
        await place_order(update, context)
    elif data == 'reenter_payment_info':
        await reenter_payment_info_handler(update, context)

    # Admin Dashboard & Inventory & Product CMS
    elif data == 'admin_panel':
        await admin_panel(update, context)
    elif data == 'admin_orders':
        await admin_orders(update, context)
    elif data.startswith('admin_orders_filter_'):
        flt = data.replace('admin_orders_filter_', '')
        await admin_orders(update, context, filter_status=flt)
    elif data.startswith('admin_manage_ord_'):
        ord_id = int(data.replace('admin_manage_ord_', ''))
        await admin_manage_order(update, context, ord_id)
    elif data.startswith('admin_gen_label_'):
        ord_id = int(data.replace('admin_gen_label_', ''))
        await admin_gen_label_callback(update, context, ord_id)
    elif data.startswith('admin_prompt_ship_'):
        ord_id = int(data.replace('admin_prompt_ship_', ''))
        await admin_ship_order_callback(update, context, ord_id)
    elif data.startswith('admin_prompt_deliv_code_'):
        ord_id = int(data.replace('admin_prompt_deliv_code_', ''))
        await admin_prompt_deliv_code_callback(update, context, ord_id)
    elif data.startswith('admin_prompt_deliv_'):
        ord_id = int(data.replace('admin_prompt_deliv_', ''))
        await admin_confirm_delivery_callback(update, context, ord_id)
    elif data == 'admin_pending':
        await admin_pending(update, context)
    elif data == 'admin_products':
        await admin_products(update, context)
    elif data == 'admin_inventory':
        await admin_inventory(update, context)
    elif data == 'admin_promos':
        await admin_promos(update, context)
    elif data == 'admin_promo_new':
        await admin_promo_wizard_start(update, context)
    elif data.startswith('promo_wiz_'):
        await admin_promo_wizard_callback(update, context, data)
    elif data.startswith('cms_togpromo_'):
        promo_id = int(data.replace('cms_togpromo_', ''))
        await cms_toggle_promo(update, context, promo_id)
    elif data == 'admin_crm':
        await admin_crm(update, context)
    elif data == 'admin_routes':
        await admin_routes(update, context)
    elif data == 'admin_broadcast_menu':
        await admin_broadcast_menu(update, context)
    elif data.startswith('bcast_target_'):
        target = data.replace('bcast_target_', '')
        await broadcast_set_target(update, context, target)
    elif data == 'bcast_confirm_send':
        await broadcast_confirm_send(update, context)

    # CMS Dynamic Product Editing Routes
    elif data.startswith('cms_edit_'):
        product_id = int(data.replace('cms_edit_', ''))
        await cms_edit_product(update, context, product_id)
    elif data.startswith('cms_setprice_'):
        product_id = int(data.replace('cms_setprice_', ''))
        context.user_data['edit_prod_id'] = product_id
        context.user_data['awaiting_new_price'] = True
        await safe_edit_text(update, context, "💰 *Edit Product Price*\n\nPlease type the new price in ETB (e.g., `2100`):")
    elif data.startswith('cms_setphoto_'):
        product_id = int(data.replace('cms_setphoto_', ''))
        context.user_data['edit_prod_id'] = product_id
        context.user_data['awaiting_new_photo'] = True
        await safe_edit_text(update, context, "🖼️ *Edit Product Photo*\n\nPlease send a new photo or type an image file path (e.g., `data/images/the-rise.png`):")
    elif data.startswith('cms_setdesc_'):
        product_id = int(data.replace('cms_setdesc_', ''))
        context.user_data['edit_prod_id'] = product_id
        context.user_data['awaiting_new_desc'] = True
        await safe_edit_text(update, context, "📝 *Edit Product Description*\n\nPlease type the new description text:")
    elif data.startswith('cms_togstock_'):
        product_id = int(data.replace('cms_togstock_', ''))
        await cms_toggle_stock(update, context, product_id)
    elif data.startswith('cms_addstock_'):
        parts = data.split('_')
        variant_id = int(parts[2])
        amt = int(parts[3])
        await cms_add_stock(update, context, variant_id, amt)
    elif data.startswith('cms_setvphoto_'):
        variant_id = int(data.replace('cms_setvphoto_', ''))
        context.user_data['edit_var_id'] = variant_id
        context.user_data['awaiting_vphoto'] = True
        await safe_edit_text(update, context, f"🖼️ *Set Variant Photo (ID #{variant_id})*\n\nPlease send a photo or type an image path (e.g. `data/images/the-rise.png`):")
    elif data.startswith('cms_setvsize_'):
        variant_id = int(data.replace('cms_setvsize_', ''))
        context.user_data['edit_var_id'] = variant_id
        context.user_data['awaiting_vsize'] = True
        await safe_edit_text(update, context, f"📐 *Set Variant Size Name (ID #{variant_id})*\n\nPlease type the size name (e.g., `Standard`, `Large`, `XL`, `Compact`):")
    elif data.startswith('cms_setvmod_'):
        variant_id = int(data.replace('cms_setvmod_', ''))
        context.user_data['edit_var_id'] = variant_id
        context.user_data['awaiting_vmod'] = True
        await safe_edit_text(update, context, f"💰 *Set Variant Price Modifier (ID #{variant_id})*\n\nPlease type price modifier in ETB (e.g., `500` for +500 ETB, `-200` for -200 ETB, `0` for none):")
    elif data.startswith('cms_addvar_'):
        product_id = int(data.replace('cms_addvar_', ''))
        context.user_data['new_var_prod_id'] = product_id
        context.user_data['new_var_step'] = 'finish'
        context.user_data['new_var_data'] = {}
        await safe_edit_text(update, context, f"➕ *Add New Custom Variant — Step 1 of 4*\n\nType the Wood Finish / Color Name:\n_Examples: 🪵 Natural Oak, 🌰 Dark Walnut, 🖤 Midnight Ash, 🎨 Custom Teak_")
    elif data.startswith('cms_setvstock_'):
        variant_id = int(data.replace('cms_setvstock_', ''))
        context.user_data['edit_var_id'] = variant_id
        context.user_data['awaiting_vstock_qty'] = True
        await safe_edit_text(update, context, f"🔢 *Set Variant Stock Quantity (ID #{variant_id})*\n\nPlease type the stock quantity in units (e.g., `10`, `0`, `25`):")
    elif data.startswith('cms_del_confirm_'):
        product_id = int(data.replace('cms_del_confirm_', ''))
        await cms_confirm_delete(update, context, product_id)
    elif data.startswith('cms_delete_'):
        product_id = int(data.replace('cms_delete_', ''))
        await cms_delete_product(update, context, product_id)
    elif data == 'cms_add_new':
        await cms_add_new_product(update, context)
    elif data == 'admin_stats':
        await admin_panel(update, context)
    elif data.startswith('verify_pay_'):
        payment_id = int(data.replace('verify_pay_', ''))
        await verify_order(update, context, payment_id)
    elif data.startswith('reject_pay_'):
        payment_id = int(data.replace('reject_pay_', ''))
        await reject_order(update, context, payment_id)

    # Dynamic routes
    elif data.startswith('category_'):
        category = data.replace('category_', '')
        await show_category(update, context, category)
    elif data.startswith('selvar_'):
        parts = data.split('_')
        product_id = int(parts[1])
        variant_id = int(parts[2])
        await show_product_detail(update, context, product_id, selected_variant_id=variant_id)
    elif data.startswith('selcolor_'):
        parts = data.split('_')
        product_id = int(parts[1])
        color_idx = int(parts[2])
        colors = ["Natural Oak", "Dark Walnut", "Midnight Ash"]
        selected_color = colors[color_idx] if color_idx < len(colors) else colors[0]
        await show_product_detail(update, context, product_id, selected_color=selected_color)
    elif data.startswith('opt_engrave_') or data.startswith('engrave_'):
        pid_str = data.replace('opt_engrave_', '').replace('engrave_', '')
        if pid_str.isdigit():
            product_id = int(pid_str)
            context.user_data['engrave_product_id'] = product_id
            from utils.keyboards import engraving_input_reply_keyboard
            await safe_edit_text(
                update, context,
                "✍️ <b>Custom Wood Engraving (+400 ETB)</b>\n\nPlease type the custom text/initials you want laser engraved into the wood:\n<i>Example: Alex M. or Oxel Studio</i>",
                parse_mode="HTML"
            )
            await query.message.reply_text(
                "👇 Tap a quick template below or type your custom text:",
                reply_markup=engraving_input_reply_keyboard()
            )
            context.user_data['awaiting_engraving'] = True
    elif data.startswith('clear_engrave_'):
        product_id = int(data.replace('clear_engrave_', ''))
        context.user_data.setdefault('engravings', {}).pop(product_id, None)
        await query.answer("✨ Engraving removed.", show_alert=True)
        await show_product_detail(update, context, product_id)
    elif data.startswith('product_'):
        product_id = int(data.replace('product_', ''))
        await show_product_detail(update, context, product_id)
    elif data.startswith('add_cart_') or data.startswith('addcart_'):
        raw = data.replace('add_cart_', '').replace('addcart_', '')
        parts = raw.split('_')
        product_id = int(parts[0])
        variant_id = int(parts[1]) if len(parts) > 1 else None
        await add_to_cart(update, context, product_id, variant_id=variant_id)
    elif data.startswith('buynow_'):
        raw = data.replace('buynow_', '')
        parts = raw.split('_')
        product_id = int(parts[0])
        variant_id = int(parts[1]) if len(parts) > 1 else None
        await add_to_cart(update, context, product_id, variant_id=variant_id)
        await checkout(update, context)
    elif data.startswith('notify_stock_'):
        await query.answer(
            "🙏 We're so sorry this piece is temporarily sold out!\n\n"
            "🔔 You're on our priority list! We will alert you the moment our craftsmen restock this finish.",
            show_alert=True
        )
    elif data.startswith('inc_'):
        index = int(data.replace('inc_', ''))
        await adjust_quantity(update, context, 'inc', index)
    elif data.startswith('dec_'):
        index = int(data.replace('dec_', ''))
        await adjust_quantity(update, context, 'dec', index)
    elif data.startswith('remove_'):
        index = int(data.replace('remove_', ''))
        await adjust_quantity(update, context, 'remove', index)
    elif data.startswith('refresh_order_'):
        order_number = data.replace('refresh_order_', '')
        await show_order_status(update, context, order_number)
    elif data.startswith('verify_order_'):
        order_id = int(data.replace('verify_order_', ''))
        await verify_order(update, context, order_id)
    elif data.startswith('reject_order_'):
        order_id = int(data.replace('reject_order_', ''))
        await reject_order(update, context, order_id)

    # ===== BUNDLE WIZARD ROUTES =====
    elif data.startswith('bundle_start_'):
        bundle_pid = int(data.replace('bundle_start_', ''))
        await bundle_start_wizard(update, context, bundle_pid)
    elif data.startswith('bundle_color_'):
        parts = data.split('_')  # bundle_color_{pid}_{step}_{color_idx}
        bundle_pid = int(parts[2])
        step = int(parts[3])
        color_idx = int(parts[4])
        await bundle_color_step(update, context, bundle_pid, step, color_idx)
    elif data.startswith('bundle_back_'):
        parts = data.split('_')  # bundle_back_{pid}_{current_step}
        bundle_pid = int(parts[2])
        current_step = int(parts[3])
        await bundle_back_step(update, context, bundle_pid, current_step)
    elif data.startswith('bundle_confirm_'):
        bundle_pid = int(data.replace('bundle_confirm_', ''))
        await bundle_confirm(update, context, bundle_pid)
    elif data.startswith('bundle_addcart_'):
        bundle_pid = int(data.replace('bundle_addcart_', ''))
        await bundle_add_to_cart(update, context, bundle_pid)

    elif data == 'noop':
        pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Always sync live Telegram user information (handle and names) to DB
    if update.effective_user:
        db = SessionLocal()
        try:
            from models.user import sync_telegram_user
            sync_telegram_user(db, update.effective_user)
        except Exception:
            pass
        finally:
            db.close()

    # Check if admin is staging a rich media broadcast message
    if context.user_data.get('awaiting_broadcast_msg'):
        await broadcast_stage_message(update, context)
        return

    # Location handler — saves GPS address then collects phone (same flow as typed address)
    if update.message.location:
        loc = update.message.location
        maps_url = f"https://maps.google.com/?q={loc.latitude:.6f},{loc.longitude:.6f}"
        address_str = f"📍 Google Maps: {maps_url}"
        context.user_data['shipping_address'] = address_str
        context.user_data['location_lat'] = loc.latitude
        context.user_data['location_lon'] = loc.longitude
        context.user_data['awaiting_address'] = False

        # Save location to DB and collect phone number next
        saved_phone = None
        db = SessionLocal()
        try:
            from models.user import sync_telegram_user
            u_rec = sync_telegram_user(db, update.effective_user)
            if u_rec:
                u_rec.saved_address_1 = address_str
                saved_phone = u_rec.phone
                db.commit()
        except Exception:
            pass
        finally:
            db.close()

        from utils.keyboards import phone_input_reply_keyboard
        await update.message.reply_text(
            f"📍 <b>Location Saved!</b>\n<a href='{maps_url}'>🗺️ Tap to Open in Google Maps</a>\n\n"
            f"📞 <b>Contact Phone Required</b>\n"
            f"Our courier team needs your number to reach you on delivery.\n\n"
            f"👇 Share your contact, use saved number, or type a new one:",
            reply_markup=phone_input_reply_keyboard(saved_phone),
            parse_mode="HTML"
        )
        context.user_data['awaiting_phone'] = True
        return

    # Photo handler (receipt or product/variant photo edit)
    if update.message.photo:
        if context.user_data.get('awaiting_receipt'):
            await process_receipt(update, context)
            return
        elif context.user_data.get('awaiting_new_photo'):
            product_id = context.user_data.get('edit_prod_id')
            photo = update.message.photo[-1]
            db = SessionLocal()
            try:
                product = db.query(Product).filter(Product.id == product_id).first()
                if product:
                    product.image_url = photo.file_id
                    db.commit()
                    await update.message.reply_text(f"✅ *Product Photo Updated for {product.name}!*", parse_mode="Markdown")
            finally:
                db.close()
            context.user_data['awaiting_new_photo'] = False
            await cms_edit_product(update, context, product_id)
            return
        elif context.user_data.get('awaiting_vphoto'):
            variant_id = context.user_data.get('edit_var_id')
            photo = update.message.photo[-1]
            db = SessionLocal()
            product_id = None
            try:
                variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
                if variant:
                    variant.image_url = photo.file_id
                    product_id = variant.product_id
                    db.commit()
                    await update.message.reply_text(f"✅ *Variant Photo Updated for {variant.finish_name}!*", parse_mode="Markdown")
            finally:
                db.close()
            context.user_data['awaiting_vphoto'] = False
            if product_id:
                await cms_edit_product(update, context, product_id)
            return

    # Contact handler (Telegram shared contact card)
    if update.message.contact:
        await process_phone(update, context)
        return

    text = update.message.text
    if not text:
        return

    # Admin Delivery Code Verification
    if context.user_data.get('awaiting_deliv_code_order_id'):
        order_id = context.user_data.pop('awaiting_deliv_code_order_id')
        typed_code = text.strip()
        db = SessionLocal()
        try:
            from database import Order
            from services.order_service import confirm_order_delivery
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                expected_code = (order.delivery_code or '').strip()
                if typed_code.upper() == expected_code.upper():
                    confirm_order_delivery(db, order.order_number, typed_code)
                    await update.message.reply_text(
                        f"✅ *DELIVERY CONFIRMED WITH CODE!*\n\nOrder #{order.order_number} marked as *DELIVERED*.\nCustomer notified!",
                        parse_mode="Markdown"
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=order.user_id,
                            text=f"🏠 *ORDER DELIVERED — THANK YOU!*\n\nYour order `#{order.order_number}` was verified and handed off.\nLeave a review anytime below or via /myorders!",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("⭐ Leave a Review Now", callback_data=f"prompt_review_{order.order_number}")],
                                [InlineKeyboardButton("📋 My Orders", callback_data="my_orders")]
                            ]),
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
                else:
                    await update.message.reply_text(
                        f"❌ *INVALID CODE! Verification failed.*\nTyped: `{typed_code}` | Code does not match order delivery code.",
                        parse_mode="Markdown"
                    )
        finally:
            db.close()
        return
    if context.user_data.get('awaiting_new_price'):
        product_id = context.user_data.get('edit_prod_id')
        try:
            new_price = int(text.strip())
            db = SessionLocal()
            try:
                product = db.query(Product).filter(Product.id == product_id).first()
                if product:
                    product.price = new_price
                    db.commit()
                    await update.message.reply_text(f"✅ *Price updated to {new_price:,} ETB for {product.name}!*", parse_mode="Markdown")
            finally:
                db.close()
        except ValueError:
            await update.message.reply_text("❌ Invalid price number.")
        context.user_data['awaiting_new_price'] = False
        await cms_edit_product(update, context, product_id)
        return

    if context.user_data.get('awaiting_new_photo'):
        product_id = context.user_data.get('edit_prod_id')
        new_img = text.strip()
        db = SessionLocal()
        try:
            product = db.query(Product).filter(Product.id == product_id).first()
            if product:
                product.image_url = new_img
                db.commit()
                await update.message.reply_text(f"✅ *Product Image updated for {product.name}!*", parse_mode="Markdown")
        finally:
            db.close()
        context.user_data['awaiting_new_photo'] = False
        await cms_edit_product(update, context, product_id)
        return

    if context.user_data.get('awaiting_vphoto'):
        variant_id = context.user_data.get('edit_var_id')
        new_img = text.strip()
        db = SessionLocal()
        product_id = None
        try:
            variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
            if variant:
                variant.image_url = new_img
                product_id = variant.product_id
                db.commit()
                await update.message.reply_text(f"✅ *Variant Photo Updated for {variant.finish_name}!*", parse_mode="Markdown")
        finally:
            db.close()
        context.user_data['awaiting_vphoto'] = False
        if product_id:
            await cms_edit_product(update, context, product_id)
        return

    if context.user_data.get('awaiting_vsize'):
        variant_id = context.user_data.get('edit_var_id')
        new_size = text.strip()
        db = SessionLocal()
        product_id = None
        try:
            variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
            if variant:
                variant.size_name = new_size if new_size.lower() != 'none' else None
                product_id = variant.product_id
                db.commit()
                await update.message.reply_text(f"✅ *Variant Size Updated to '{new_size}' for {variant.finish_name}!*", parse_mode="Markdown")
        finally:
            db.close()
        context.user_data['awaiting_vsize'] = False
        if product_id:
            await cms_edit_product(update, context, product_id)
        return

    if context.user_data.get('awaiting_vmod'):
        variant_id = context.user_data.get('edit_var_id')
        try:
            new_mod = int(text.strip())
            db = SessionLocal()
            product_id = None
            try:
                variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
                if variant:
                    variant.price_modifier = new_mod
                    product_id = variant.product_id
                    db.commit()
                    await update.message.reply_text(f"✅ *Price Modifier set to {new_mod:+} ETB for {variant.finish_name}!*", parse_mode="Markdown")
            finally:
                db.close()
            context.user_data['awaiting_vmod'] = False
            if product_id:
                await cms_edit_product(update, context, product_id)
            return
        except ValueError:
            await update.message.reply_text("❌ Invalid price modifier number. Enter e.g. `500` or `-200` or `0`.")
            return

    # ===== ADD NEW CUSTOM VARIANT WIZARD =====
    if context.user_data.get('new_var_step'):
        step = context.user_data['new_var_step']
        prod_id = context.user_data.get('new_var_prod_id')
        var_data = context.user_data.setdefault('new_var_data', {})
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cms_edit_{prod_id}")]])

        if step == 'finish':
            var_data['finish_name'] = text.strip()
            context.user_data['new_var_step'] = 'size'
            await update.message.reply_text(
                "✅ Finish name saved!\n\n➕ *Step 2 of 4 — Size Name*\n\nType size name (e.g. `Standard`, `Large`, `XL`) or type `none` to skip:",
                reply_markup=cancel_kb, parse_mode="Markdown"
            )
            return

        elif step == 'size':
            size_val = text.strip()
            var_data['size_name'] = None if size_val.lower() == 'none' else size_val
            context.user_data['new_var_step'] = 'price_mod'
            await update.message.reply_text(
                "✅ Size saved!\n\n➕ *Step 3 of 4 — Price Modifier (+/- ETB)*\n\nType price modifier offset in ETB (e.g. `500` for +500 ETB, `0` for none):",
                reply_markup=cancel_kb, parse_mode="Markdown"
            )
            return

        elif step == 'price_mod':
            try:
                mod_val = int(text.strip())
                var_data['price_modifier'] = mod_val
                context.user_data['new_var_step'] = 'stock'
                await update.message.reply_text(
                    f"✅ Price modifier saved ({mod_val:+} ETB)!\n\n➕ *Step 4 of 4 — Stock Quantity*\n\nType initial stock quantity (number of units):",
                    reply_markup=cancel_kb, parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text("❌ Price modifier must be a number (e.g. `500` or `0`). Try again:")
            return

        elif step == 'stock':
            try:
                stock_val = int(text.strip())
                var_data['stock_quantity'] = stock_val
                context.user_data['new_var_step'] = None

                db = SessionLocal()
                try:
                    from services.admin_service import add_product_variant
                    new_v = add_product_variant(
                        db,
                        admin_id=update.effective_user.id,
                        product_id=prod_id,
                        finish_name=var_data.get('finish_name', 'Custom Finish'),
                        stock_quantity=stock_val,
                        price_modifier=var_data.get('price_modifier', 0),
                        size_name=var_data.get('size_name')
                    )
                    await update.message.reply_text(
                        f"🎉 *Custom Variant Created!*\n\nFinish: *{new_v.finish_name}*\nSize: *{new_v.size_name or 'Standard'}*\nStock: *{stock_val} units*\nPrice Mod: *{new_v.price_modifier:+} ETB*",
                        parse_mode="Markdown"
                    )
                finally:
                    db.close()

                await cms_edit_product(update, context, prod_id)
                return
            except ValueError:
                await update.message.reply_text("❌ Stock quantity must be a number (e.g. `10`). Try again:")
            return

    if context.user_data.get('awaiting_new_desc'):
        product_id = context.user_data.get('edit_prod_id')
        new_desc = text.strip()
        db = SessionLocal()
        try:
            product = db.query(Product).filter(Product.id == product_id).first()
            if product:
                product.description = new_desc
                db.commit()
                await update.message.reply_text(f"✅ *Description updated for {product.name}!*", parse_mode="Markdown")
        finally:
            db.close()
        context.user_data['awaiting_new_desc'] = False
        await cms_edit_product(update, context, product_id)
        return

    # ===== SET EXACT VARIANT STOCK QUANTITY (Admin) =====
    if context.user_data.get('awaiting_vstock_qty'):
        variant_id = context.user_data.get('edit_var_id')
        try:
            new_qty = int(text.strip())
            if new_qty < 0:
                await update.message.reply_text("❌ Stock quantity cannot be negative. Please enter 0 or higher.")
                return
            db = SessionLocal()
            product_id = None
            try:
                variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
                if variant:
                    variant.stock_quantity = new_qty
                    db.commit()
                    product_id = variant.product_id
                    badge = "🔴 Out of Stock" if new_qty == 0 else ("🟡 Low Stock" if new_qty < 4 else "🟢 In Stock")
                    await update.message.reply_text(
                        f"✅ *Stock Updated!*\n\n{variant.finish_name}: *{new_qty} units* [{badge}]",
                        parse_mode="Markdown"
                    )
            finally:
                db.close()
            context.user_data['awaiting_vstock_qty'] = False
            if product_id:
                await cms_edit_product(update, context, product_id)
            return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number (e.g. `0`, `2`, `15`).", parse_mode="Markdown")
            return

    # ===== ADD NEW PRODUCT WIZARD (Admin) =====
    if context.user_data.get('new_product_step'):
        step = context.user_data['new_product_step']
        product_data = context.user_data.setdefault('new_product', {})
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_products")]])

        if step == 'name':
            product_data['name'] = text.strip()
            context.user_data['new_product_step'] = 'category'
            await update.message.reply_text(
                "✅ Name saved!\n\n➕ *Step 2 of 4 — Category*\n\nType the product category:\n_Examples: Laptop Stand, Phone Holder, Desk Mat_",
                reply_markup=cancel_kb, parse_mode="Markdown"
            )
            return

        elif step == 'category':
            product_data['category'] = text.strip()
            context.user_data['new_product_step'] = 'price'
            await update.message.reply_text(
                "✅ Category saved!\n\n➕ *Step 3 of 4 — Price*\n\nType the price in ETB (numbers only):\n_Example: 1890_",
                reply_markup=cancel_kb, parse_mode="Markdown"
            )
            return

        elif step == 'price':
            try:
                price = int(text.strip())
                product_data['price'] = price
                context.user_data['new_product_step'] = 'description'
                await update.message.reply_text(
                    f"✅ Price saved: *{price:,} ETB*\n\n➕ *Step 4 of 4 — Description*\n\nType a short product description:",
                    reply_markup=cancel_kb, parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text("❌ Price must be a number. Try again (e.g. `1890`):", parse_mode="Markdown")
            return

        elif step == 'description':
            product_data['description'] = text.strip()
            context.user_data['new_product_step'] = None

            # Create the product
            name = product_data.get('name', 'Unnamed Product')
            category = product_data.get('category', 'General')
            price = product_data.get('price', 0)
            desc = product_data.get('description', '')
            slug = name.lower().replace(' ', '-').replace('—', '').replace('  ', '-')

            db = SessionLocal()
            try:
                new_p = Product(
                    name=name, slug=slug, category=category,
                    price=price, description=desc,
                    image_url='data/images/the-rise.png', in_stock=True
                )
                db.add(new_p)
                db.commit()
                db.refresh(new_p)

                for finish in ["Natural Oak", "Dark Walnut", "Midnight Ash"]:
                    db.add(ProductVariant(product_id=new_p.id, finish_name=finish, stock_quantity=10))
                db.commit()

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✏️ Edit {name} Now", callback_data=f"cms_edit_{new_p.id}")],
                    [InlineKeyboardButton("🪵 Back to CMS", callback_data="admin_products")]
                ])
                await update.message.reply_text(
                    f"🎉 *Product Created Successfully!*\n━━━━━━━━━━━━━━━━━━━━\n📦 *{name}* (ID: `{new_p.id}`)\n💰 Price: {price:,} ETB\n📂 Category: {category}\n\n✅ 3 finish variants added (Natural Oak, Dark Walnut, Midnight Ash) with 10 units each.\n\nYou can now edit the photo and fine-tune stock levels 👇",
                    reply_markup=keyboard, parse_mode="Markdown"
                )
            except Exception as e:
                await update.message.reply_text(f"❌ Error creating product: {str(e)}")
            finally:
                db.close()
            return

    # ===== ADMIN PROMO CREATION WIZARD (text steps) =====
    if context.user_data.get('promo_wiz_step'):
        step = context.user_data['promo_wiz_step']
        wiz = context.user_data.setdefault('promo_wiz_data', {})
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_promos")]])

        if step == 'code':
            code = text.strip().upper().replace(' ', '')
            if not code:
                await update.message.reply_text("❌ Code cannot be empty. Try again:", reply_markup=cancel_kb)
                return
            wiz['code'] = code
            context.user_data['promo_wiz_step'] = 'discount'
            await update.message.reply_text(
                f"✅ Code: `{code}`\n\n*Step 2 — Discount*\nType discount value:\n`20%` for percent, `500` (number only) for fixed ETB",
                reply_markup=cancel_kb, parse_mode="Markdown"
            )
            return

        elif step == 'discount':
            raw = text.strip().replace('%', '')
            try:
                val = int(raw)
                if '%' in text or val <= 100:
                    wiz['discount_percent'] = val
                    wiz['discount_amount'] = 0
                    disc_str = f"{val}% off"
                else:
                    wiz['discount_amount'] = val
                    wiz['discount_percent'] = 0
                    disc_str = f"{val} ETB off"
            except ValueError:
                await update.message.reply_text("❌ Invalid. Type e.g. `20%` or `500`. Try again:", reply_markup=cancel_kb)
                return
            wiz['disc_str'] = disc_str
            context.user_data['promo_wiz_step'] = 'max_uses'
            await update.message.reply_text(
                f"✅ Discount: *{disc_str}*\n\n*Step 3 — Max Total Uses*\nHow many users can use this promo in total?\n`0` or `skip` = unlimited",
                reply_markup=cancel_kb, parse_mode="Markdown"
            )
            return

        elif step == 'max_uses':
            raw = text.strip().lower()
            if raw in ('0', 'skip', 'none', 'unlimited'):
                wiz['max_uses'] = None
            else:
                try:
                    wiz['max_uses'] = int(raw)
                except ValueError:
                    await update.message.reply_text("❌ Enter a number or `skip`. Try again:", reply_markup=cancel_kb)
                    return
            context.user_data['promo_wiz_step'] = 'products'
            # Fetch products for reference
            db = SessionLocal()
            try:
                prods = db.query(Product).filter(Product.in_stock == True).all()
                prod_list = '\n'.join([f"  `{p.id}` — {p.name}" for p in prods]) or '  (no products)'
            finally:
                db.close()
            await update.message.reply_text(
                f"✅ Max uses: *{wiz['max_uses'] or 'Unlimited'}*\n\n*Step 4 — Product Restriction*\nWhich product IDs should this promo apply to?\nAvailable products:\n{prod_list}\n\nType product IDs separated by commas (e.g. `1,3`) or `skip` for all products.",
                reply_markup=cancel_kb, parse_mode="Markdown"
            )
            return

        elif step == 'products':
            raw = text.strip().lower()
            if raw in ('skip', 'all', 'none', '0'):
                wiz['allowed_product_ids'] = None
            else:
                ids = [p.strip() for p in text.split(',') if p.strip().isdigit()]
                wiz['allowed_product_ids'] = ','.join(ids) if ids else None
            context.user_data['promo_wiz_step'] = 'tier'
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🥉 All (Bronze+)", callback_data="promo_wiz_tier_none"),
                 InlineKeyboardButton("🥈 Silver+", callback_data="promo_wiz_tier_silver")],
                [InlineKeyboardButton("🥇 Gold Only", callback_data="promo_wiz_tier_gold")]
            ])
            prod_str = f"IDs: {wiz['allowed_product_ids']}" if wiz.get('allowed_product_ids') else 'All products'
            await update.message.reply_text(
                f"✅ Products: *{prod_str}*\n\n*Step 5 — Loyalty Tier Requirement*\nSelect minimum loyalty tier:",
                reply_markup=keyboard, parse_mode="Markdown"
            )
            return

    # ─────────────────────────────────────────────
    # TYPING BAR KEYBOARD BUTTON ROUTER
    # ─────────────────────────────────────────────
    text_clean = text.strip()

    # Cancel Checkout Action
    if text_clean == "❌ Cancel Checkout":
        context.user_data['awaiting_address'] = False
        context.user_data['awaiting_phone'] = False
        context.user_data.pop('_address_override', None)
        from utils.keyboards import persistent_reply_keyboard
        await update.message.reply_text(
            "❌ <b>Checkout Cancelled.</b> You can continue browsing or return to your cart anytime.",
            reply_markup=persistent_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    # Cancel Promo Entry
    if text_clean == "❌ Cancel Promo Entry":
        context.user_data['awaiting_promo'] = False
        await view_cart(update, context)
        return

    # Cancel Engraving Entry
    if text_clean == "❌ Cancel Engraving":
        context.user_data['awaiting_engraving'] = False
        pid = context.user_data.get('engrave_product_id')
        if pid:
            await show_product_detail(update, context, pid)
        else:
            await catalog_command(update, context)
        return

    # Main Typing Bar Navigation Buttons
    if text_clean in ("📦 Browse Catalog", "📦 Browse Products", "📦 Catalog"):
        await catalog_command(update, context)
        return
    elif text_clean in ("🛒 View Cart", "🛒 My Cart", "🛒 Cart"):
        await view_cart(update, context)
        return
    elif text_clean in ("📋 My Orders", "📋 Orders"):
        await my_orders(update, context)
        return
    elif text_clean in ("👤 Profile & VIP", "👤 My Profile & VIP", "👤 Profile"):
        await user_profile_menu(update, context)
        return
    elif text_clean in ("🏅 Loyalty Points", "🏅 Loyalty"):
        await loyalty_menu(update, context)
        return
    elif text_clean in ("📞 Contact Support", "📞 Support"):
        from utils.keyboards import persistent_reply_keyboard
        from config import TELEGRAM_CHANNEL, INSTAGRAM_URL, TIKTOK_URL
        contact_text = (
            "<b>📞 Contact Support</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Our team will respond within 24 hours.\n\n"
            f"📢 Telegram: {TELEGRAM_CHANNEL}\n"
            f"📸 Instagram: {INSTAGRAM_URL}\n"
            f"🎵 TikTok: {TIKTOK_URL}\n"
            "📧 Contact us via Telegram for support\n\n"
            "🕐 Mon–Fri: 9:00 AM – 6:00 PM EAT"
        )
        await update.message.reply_text(
            contact_text,
            reply_markup=persistent_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    # Saved Address Entry at Checkout
    if context.user_data.get('awaiting_address'):
        user_id = update.effective_user.id
        if text_clean.startswith("🏠 Primary:") or text_clean.startswith("🏠"):
            # Fetch full saved address — update.message.text is read-only in PTB v20
            # so we store in context for process_address to pick up
            addr = context.user_data.get('saved_addr1_full')
            if not addr:
                db = SessionLocal()
                try:
                    u = db.query(User).filter(User.user_id == user_id).first()
                    if u and u.saved_address_1:
                        addr = u.saved_address_1
                finally:
                    db.close()
            if addr:
                context.user_data['_address_override'] = addr

        elif text_clean.startswith("🏢 Secondary:") or text_clean.startswith("🏢"):
            addr = context.user_data.get('saved_addr2_full')
            if not addr:
                db = SessionLocal()
                try:
                    u = db.query(User).filter(User.user_id == user_id).first()
                    if u and u.saved_address_2:
                        addr = u.saved_address_2
                finally:
                    db.close()
            if addr:
                context.user_data['_address_override'] = addr

        await process_address(update, context)
        return

    # Contact Phone Entry at Checkout
    if context.user_data.get('awaiting_phone') or (update.message and update.message.contact):
        await process_phone(update, context)
        return

    # Saved Address Entry (Profile)
    if context.user_data.get('awaiting_addr1'):
        user_id = update.effective_user.id
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.user_id == user_id).first()
            if u:
                u.saved_address_1 = text.strip()
                db.commit()
                await update.message.reply_text("✅ <b>Primary Address #1 Saved!</b>", parse_mode="HTML")
        finally:
            db.close()
        context.user_data['awaiting_addr1'] = False
        await user_profile_menu(update, context)
        return

    if context.user_data.get('awaiting_addr2'):
        user_id = update.effective_user.id
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.user_id == user_id).first()
            if u:
                u.saved_address_2 = text.strip()
                db.commit()
                await update.message.reply_text("✅ <b>Secondary Address #2 Saved!</b>", parse_mode="HTML")
        finally:
            db.close()
        context.user_data['awaiting_addr2'] = False
        await user_profile_menu(update, context)
        return

    # Engraving entry
    if context.user_data.get('awaiting_engraving'):
        product_id = context.user_data.get('engrave_product_id')
        if 'engravings' not in context.user_data:
            context.user_data['engravings'] = {}

        eng_val = text.strip()
        if eng_val.startswith("✨ "):
            eng_val = eng_val[2:].strip()
        elif eng_val.startswith("✨"):
            eng_val = eng_val[1:].strip()

        context.user_data['engravings'][product_id] = eng_val
        context.user_data['awaiting_engraving'] = False

        from utils.keyboards import persistent_reply_keyboard
        await update.message.reply_text(
            f"✨ <b>Custom Wood Engraving Saved!</b>\n\nText: <code>{html.escape(eng_val)}</code> (+400 ETB)",
            reply_markup=persistent_reply_keyboard(),
            parse_mode="HTML"
        )
        await show_product_detail(update, context, product_id)
        return

    # Promo code entry
    if context.user_data.get('awaiting_promo'):
        raw_code = text.strip()
        for prefix in ("🎟️ ", "🏅 ", "🎟️", "🏅"):
            if raw_code.startswith(prefix):
                raw_code = raw_code.replace(prefix, "").strip()

        context.user_data['awaiting_promo'] = False

        # Special: MYPOINTS redeems loyalty points
        if 'MYPOINTS' in raw_code.upper():
            disc = redeem_points_for_discount(update.effective_user.id)
            if disc > 0:
                context.user_data['applied_promo'] = 'MYPOINTS (Loyalty)'
                context.user_data['discount_amount'] = disc
                await update.message.reply_text(
                    f"🏅 <b>Loyalty Points Redeemed!</b>\n\nDiscount: -{disc:,} ETB applied to your cart!",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    "⚠️ <b>No redeemable points yet.</b>\n\nEarn points by placing orders (1 pt per 100 ETB spent).",
                    parse_mode="HTML"
                )
            await view_cart(update, context)
            return

        code_input = raw_code.replace(" ", "").upper()
        db = SessionLocal()
        try:
            summary = get_cart_summary(db, update.effective_user.id)
            subtotal = summary['subtotal']
            cart_product_ids = [item['product_id'] for item in summary.get('items', [])]
            promo_res = validate_promo_code(db, code_input, update.effective_user.id, subtotal,
                                           cart_product_ids=cart_product_ids)

            if promo_res['valid']:
                context.user_data['applied_promo'] = code_input
                context.user_data['discount_amount'] = promo_res['discount_amount']

                await update.message.reply_text(
                    f"🎉 <b>Promo Code Applied!</b>\n\nCode: <code>{code_input}</code>\nDiscount: -{promo_res['discount_amount']:,} ETB",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    f"❌ <b>Invalid Promo Code</b>\n\n{html.escape(promo_res['message'])}\n\n💡 Tap 🏅 MYPOINTS to redeem your loyalty points!",
                    parse_mode="HTML"
                )
        finally:
            db.close()

        await view_cart(update, context)
        return

    # Reference entry
    if context.user_data.get('awaiting_reference'):
        await process_reference(update, context)
        return

    # Tracking entry
    if context.user_data.get('awaiting_tracking'):
        await process_tracking(update, context)
        return

    # Default response with persistent typing area keyboard
    from utils.keyboards import persistent_reply_keyboard
    await update.message.reply_text(
        "🤔 I didn't understand that.\n\nTap a quick button on your keyboard below, or use /start:",
        reply_markup=persistent_reply_keyboard()
    )


# ===== TRACK COMMAND =====

async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        order_number = context.args[0].upper()
        await show_order_status(update, context, order_number)
    else:
        await track_order(update, context)


# ===== MAIN =====

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Please configure your .env file.")
        sys.exit(1)

    logger.info("Initializing database...")
    create_tables()
    seed_products()

    logger.info("Starting Oxel Bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('about', about_command))
    app.add_handler(CommandHandler('catalog', catalog_command))
    app.add_handler(CommandHandler('cart', view_cart))
    app.add_handler(CommandHandler('clearcart', clear_cart_command))
    app.add_handler(CommandHandler('track', track_command))
    app.add_handler(CommandHandler('orders', my_orders))
    app.add_handler(CommandHandler('myorders', my_orders))
    app.add_handler(CommandHandler('loyalty', loyalty_menu))
    app.add_handler(CommandHandler('profile', user_profile_menu))

    # Admin commands
    app.add_handler(CommandHandler('admin', admin_panel))
    app.add_handler(CommandHandler('products', admin_products))
    app.add_handler(CommandHandler('promos', admin_promos))
    app.add_handler(CommandHandler('setstock', setstock_command))
    app.add_handler(CommandHandler('addproduct', addproduct_command))
    app.add_handler(CommandHandler('addpromo', addpromo_command))
    app.add_handler(CommandHandler('status', status_command))
    app.add_handler(CommandHandler('ship', ship_command))
    app.add_handler(CommandHandler('bulkship', bulkship_command))
    app.add_handler(CommandHandler('shipping_label', shipping_label_command))
    app.add_handler(CommandHandler('confirm_delivery', confirm_delivery_command))
    app.add_handler(CommandHandler('givepoints', givepoints_command))
    app.add_handler(CommandHandler('userinfo', userinfo_command))
    app.add_handler(CommandHandler('broadcast', broadcast_command))
    app.add_handler(CommandHandler('broadcast_vip', broadcast_vip_command))

    # Callback query handler
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Message handlers — order matters: specific types first
    app.add_handler(MessageHandler(filters.LOCATION, handle_message))
    app.add_handler(MessageHandler(filters.CONTACT, handle_message))  # phone sharing at checkout
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    app.add_handler(MessageHandler(filters.VIDEO, handle_message))
    app.add_handler(MessageHandler(filters.AUDIO, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_message))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_message))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
