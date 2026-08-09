import html
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, Product, ProductVariant
from services.cart_service import (
    add_to_cart as service_add_to_cart,
    get_cart_summary,
    remove_from_cart as service_remove_from_cart,
    update_cart_item_quantity
)
from services.promo_service import validate_promo_code
from utils.safe_message import safe_edit_text

logger = logging.getLogger(__name__)


async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int, variant_id: int = None):
    """Handler for adding item to user's persistent cart."""
    query = update.callback_query
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            await query.answer("Product not found!", show_alert=True)
            return

        user_sel = context.user_data.get('selected_variants', {}).get(product_id, {})
        target_var_id = variant_id or user_sel.get('variant_id')

        if target_var_id:
            variant = db.query(ProductVariant).filter(ProductVariant.id == target_var_id).first()
        else:
            selected_options = context.user_data.get('selected_options', {})
            selected_color = selected_options.get(product_id, "Natural Oak")
            variant = db.query(ProductVariant).filter(
                ProductVariant.product_id == product_id,
                ProductVariant.finish_name == selected_color
            ).first()

        variant_id = variant.id if variant else None
        variant_desc = variant.finish_name if variant else "Standard"
        if variant and variant.size_name:
            variant_desc += f", Size: {variant.size_name}"

        engraving_text = context.user_data.get('engravings', {}).get(product_id)

        # Add to persistent database cart via cart service
        try:
            service_add_to_cart(
                db,
                user_id=user_id,
                product_id=product_id,
                variant_id=variant_id,
                quantity=1,
                customization=engraving_text
            )
        except Exception as e:
            logger.exception(f"Error adding product {product_id} to cart for user {user_id}")
            await query.answer("❌ Error adding product to cart.", show_alert=True)
            return

        summary = get_cart_summary(db, user_id)
        await query.answer(f"✅ {product.name} ({variant_desc}) added to cart!", show_alert=False)

        from utils.recommender import get_recommendation_for_product
        rec = get_recommendation_for_product(product_id)

        rec_text = f"\n\n💡 <b>Frequently Bought Together:</b> {html.escape(rec['name'])} ({rec['price']:,} ETB)" if rec else ""
        engrave_lbl = f"\n✨ <b>Custom Engraving:</b> <code>{html.escape(engraving_text)}</code> (+400 ETB)" if engraving_text else ""
        msg_text = (
            f"✅ <b>Added to Cart!</b>\n\n"
            f"🛒 <b>{html.escape(product.name)}</b>\n"
            f"🎨 Variation: {html.escape(variant_desc)}{engrave_lbl}\n"
            f"\n📦 <b>{summary['total_items']} item{'s' if summary['total_items'] > 1 else ''}</b> in cart · "
            f"Subtotal: <b>{summary['subtotal']:,} ETB</b>{rec_text}"
        )

        buttons = []
        if rec:
            buttons.append([InlineKeyboardButton(f"🎁 Add Suggested: {rec['name']} ({rec['price']:,} ETB)", callback_data=f"product_{rec['id']}")])
        buttons.extend([
            [InlineKeyboardButton("🛒 View Cart", callback_data="view_cart")],
            [InlineKeyboardButton("📦 Keep Shopping", callback_data="catalog")],
            [InlineKeyboardButton("💳 Checkout Now", callback_data="checkout")]
        ])

        try:
            await query.edit_message_caption(caption=msg_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        except Exception:
            await query.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    finally:
        db.close()


async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for viewing user's persistent cart."""
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        summary = get_cart_summary(db, user_id)
        if not summary['items']:
            text = "🛒 <b>Your Cart is Empty</b>\n\nBrowse our catalog to add items!"
            keyboard = [[InlineKeyboardButton("📦 Browse Products", callback_data="catalog")]]
        else:
            items_text = ""
            for i, item in enumerate(summary['items'], 1):
                var_info = []
                if item.get('finish_name'):
                    var_info.append(html.escape(item['finish_name']))
                if item.get('size_name'):
                    var_info.append(f"Size: {html.escape(item['size_name'])}")
                finish_str = f" ({', '.join(var_info)})" if var_info else ""
                custom_raw = item.get('customization', '')
                # Bundle tag is stored as "[Bundle Name]" — render as group label
                is_bundle_item = bool(custom_raw and custom_raw.startswith('[') and custom_raw.endswith(']'))
                if is_bundle_item:
                    custom_str = f"\n   🎁 Part of {html.escape(custom_raw)}"
                elif custom_raw:
                    custom_str = f"\n   ✨ Customization: <code>{html.escape(custom_raw)}</code>"
                else:
                    custom_str = ""
                stock_warn = " ⚠️ OUT OF STOCK" if not item['stock_available'] else ""
                items_text += (
                    f"{i}. <b>{html.escape(item['product_name'])}</b>{finish_str}{stock_warn}{custom_str}\n"
                    f"   {item['quantity']}× · {item['unit_price']:,} ETB = <b>{item['subtotal']:,} ETB</b>\n\n"
                )

            # Compute bundle group summary
            bundle_groups = {}
            standalone_count = 0
            for item in summary['items']:
                custom_raw = item.get('customization', '')
                if custom_raw and custom_raw.startswith('[') and custom_raw.endswith(']'):
                    bundle_groups[custom_raw] = bundle_groups.get(custom_raw, 0) + 1
                else:
                    standalone_count += 1
            group_summary = ""
            for bname, cnt in bundle_groups.items():
                group_summary += f"  🎁 {html.escape(bname)}: {cnt} item(s)\n"
            if standalone_count:
                group_summary += f"  📦 Individual items: {standalone_count}\n"

            promo_code = context.user_data.get('applied_promo')
            discount_amount = 0
            if promo_code:
                res = validate_promo_code(db, promo_code, user_id, summary['subtotal'])
                if res['valid']:
                    discount_amount = res['discount_amount']
                else:
                    context.user_data.pop('applied_promo', None)

            final_total = max(0, summary['subtotal'] - discount_amount)
            promo_line = f"🎟️ <b>Promo Discount ({html.escape(str(promo_code))}):</b> -{discount_amount:,} ETB\n" if discount_amount > 0 else ""

            text = (
                f"🛒 <b>Your Shopping Cart</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{items_text}"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{group_summary}"
                f"{promo_line}"
                f"💰 <b>Total Amount: {final_total:,} ETB</b>"
            )

            keyboard = [
                [InlineKeyboardButton("💳 Checkout", callback_data="checkout")],
                [InlineKeyboardButton("🎟️ Apply Promo Code", callback_data="apply_promo")],
                [InlineKeyboardButton("✏️ Adjust Quantities", callback_data="update_cart")],
                [InlineKeyboardButton("📦 Keep Shopping", callback_data="catalog")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]

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


async def update_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for showing cart quantity adjustment keyboard."""
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        summary = get_cart_summary(db, user_id)
        if not summary['items']:
            await view_cart(update, context)
            return

        keyboard = []
        for item in summary['items']:
            cart_item_id = item['cart_item_id']
            finish_str = f" [{item['finish_name']}]" if item['finish_name'] else ""
            keyboard.append([
                InlineKeyboardButton("➖", callback_data=f"dec_{cart_item_id}"),
                InlineKeyboardButton(f"{item['quantity']}× {item['product_name']}{finish_str}", callback_data="noop"),
                InlineKeyboardButton("➕", callback_data=f"inc_{cart_item_id}")
            ])
            keyboard.append([
                InlineKeyboardButton(f"🗑 Remove {item['product_name']}", callback_data=f"remove_{cart_item_id}")
            ])

        keyboard.append([InlineKeyboardButton("💳 Checkout", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Cart", callback_data="view_cart")])

        await safe_edit_text(
            update, context,
            f"✏️ *Update Cart*\n\nSubtotal: *{summary['subtotal']:,} ETB*\n\nUse ➕/➖ to adjust quantities:",
            InlineKeyboardMarkup(keyboard)
        )
    finally:
        db.close()


async def adjust_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, cart_item_id: int):
    """Adjust quantity of item in persistent DB cart."""
    query = update.callback_query
    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        summary = get_cart_summary(db, user_id)
        item = next((i for i in summary['items'] if i['cart_item_id'] == cart_item_id), None)

        if not item:
            await query.answer("Item not found!")
            return

        if action == 'inc':
            new_qty = item['quantity'] + 1
            update_cart_item_quantity(db, user_id, cart_item_id, new_qty)
            await query.answer(f"Quantity: {new_qty}")
        elif action == 'dec':
            if item['quantity'] > 1:
                new_qty = item['quantity'] - 1
                update_cart_item_quantity(db, user_id, cart_item_id, new_qty)
                await query.answer(f"Quantity: {new_qty}")
            else:
                await query.answer("Minimum quantity is 1.", show_alert=True)
                return
        elif action == 'remove':
            service_remove_from_cart(db, user_id, cart_item_id)
            await query.answer(f"🗑 {item['product_name']} removed!")

        summary_after = get_cart_summary(db, user_id)
        if not summary_after['items']:
            await view_cart(update, context)
        else:
            await update_cart_handler(update, context)
    finally:
        db.close()
