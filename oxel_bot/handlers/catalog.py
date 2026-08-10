import os
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, Product, ProductVariant
from utils.keyboards import catalog_keyboard
from utils.safe_message import safe_edit_text
from utils.bundle_config import is_bundle


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "<b>📦 Product Catalog</b>\n\nSelect a category to browse:"

    if update.callback_query:
        await safe_edit_text(update, context, text, catalog_keyboard(), parse_mode="HTML")
    else:
        await update.message.reply_text(
            text,
            reply_markup=catalog_keyboard(),
            parse_mode="HTML"
        )


async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    db = SessionLocal()

    try:
        category_map = {
            'laptop': 'Laptop Stand',
            'phone': 'Phone Holder',
            'controller': 'Controller Holder',
            'keyboard': 'Keyboard Riser',
            'mat': 'Desk Mat',
            'headphone': 'Headphone Stand',
            'bundle': 'Bundle'
        }

        if category == 'all':
            products = db.query(Product).filter(Product.in_stock == True).all()
            msg_title = "📦 <b>All Oxel Products</b>"
        elif category == 'bundle':
            products = db.query(Product).filter(
                Product.category == 'Bundle', Product.in_stock == True
            ).all()
            msg_title = "🎁 <b>Curated Bundles (Save 15%)</b>"
        else:
            cat_name = category_map.get(category, '')
            products = db.query(Product).filter(
                Product.category == cat_name, Product.in_stock == True
            ).all()
            msg_title = f"📦 <b>{cat_name}s</b>"

        if not products:
            msg_text = (
                "🙏 <b>We're Currently Restocking!</b>\n\n"
                "Sorry, all items in this section are currently sold out due to high demand. Our craftsmen are actively hand-carving new inventory!\n\n"
                "💬 <b>Need a custom piece or pre-order?</b>\n"
                "Tap below to chat directly with our team — we'll prioritize your request!"
            )
            keyboard = [
                [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("🔙 Back to Catalog", callback_data="catalog")]
            ]
            await safe_edit_text(update, context, msg_text, InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        keyboard = []
        for p in products:
            rating_str = f" ⭐ {p.avg_rating:.1f}" if p.avg_rating else ""
            keyboard.append([InlineKeyboardButton(
                f"📦 {p.name} — {p.price:,} ETB{rating_str}", callback_data=f"product_{p.id}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Back to Catalog", callback_data="catalog")])

        msg_text = f"{msg_title}\n\nSelect a product to view photo, finishes & stock:"
        markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_text(update, context, msg_text, markup, parse_mode="HTML")
    finally:
        db.close()


async def show_product_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    product_id: int,
    selected_color: str = None,
    selected_size: str = None,
    selected_variant_id: int = None
):
    query = update.callback_query
    db = SessionLocal()

    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            await query.answer("❌ Product not found.", show_alert=True)
            return

        # Route bundles to the bundle customization wizard
        if is_bundle(product):
            db.close()
            from handlers.bundle import show_bundle_detail
            await show_bundle_detail(update, context, product_id)
            return

        variants = db.query(ProductVariant).filter(
            ProductVariant.product_id == product.id, ProductVariant.is_active == True
        ).all()

        if not variants:
            default_v = ProductVariant(product_id=product.id, finish_name="Natural Oak", stock_quantity=10)
            db.add(default_v)
            db.commit()
            db.refresh(default_v)
            variants = [default_v]

        user_sel = context.user_data.setdefault('selected_variants', {}).setdefault(product_id, {})
        
        if selected_variant_id:
            sel_variant = next((v for v in variants if v.id == selected_variant_id), variants[0])
        elif selected_color or selected_size:
            sel_variant = None
            if selected_color and selected_size:
                sel_variant = next((v for v in variants if v.finish_name == selected_color and v.size_name == selected_size), None)
            if not sel_variant and selected_color:
                sel_variant = next((v for v in variants if v.finish_name == selected_color), None)
            if not sel_variant and selected_size:
                sel_variant = next((v for v in variants if v.size_name == selected_size), None)
            if not sel_variant:
                sel_variant = variants[0]
        else:
            prev_var_id = user_sel.get('variant_id')
            sel_variant = next((v for v in variants if v.id == prev_var_id), variants[0])

        user_sel['variant_id'] = sel_variant.id
        user_sel['color'] = sel_variant.finish_name
        user_sel['size'] = sel_variant.size_name

        selected_color = sel_variant.finish_name
        selected_size = sel_variant.size_name

        price_mod = sel_variant.price_modifier or 0
        effective_unit_price = product.price + price_mod
        current_stock = sel_variant.stock_quantity
        if current_stock == 0:
            stock_badge = "🔴 <b>TEMPORARILY SOLD OUT</b> (Restocking batch)"
        elif current_stock < 4:
            stock_badge = f"⚡ <b>LOW STOCK! Only {current_stock} left!</b>"
        else:
            stock_badge = f"✅ <b>IN STOCK ({current_stock} available)</b>"

        engraving_selected = context.user_data.get('engravings', {}).get(product_id)
        engraving_status = f"✨ <b>Custom Wood Engraving:</b> <code>{html.escape(engraving_selected)}</code> (+400 ETB)" if engraving_selected else "✨ <b>Custom Engraving:</b> Not added (+400 ETB)"

        rating_val = product.avg_rating or 5.0
        review_cnt = product.review_count or 1
        full_stars = round(rating_val)
        stars_icon = "⭐" * full_stars
        rating_display = f"{stars_icon} <b>{rating_val:.1f} / 5.0</b> ({review_cnt:,} reviews)"

        active_image = sel_variant.image_url or product.image_url
        size_display = f"\n📐 <b>Selected Size:</b> <b>{html.escape(selected_size)}</b>" if selected_size else ""
        price_mod_display = f" <i>({price_mod:+} ETB)</i>" if price_mod != 0 else ""

        pname = html.escape(product.name)
        pcat = html.escape(product.category or '')
        pdesc = html.escape(product.description or '')
        scolor = html.escape(selected_color or '')

        text = (
            f"<b>{pname}</b>\n"
            f"<i>Tools for the Digital Craft</i>\n\n"
            f"💰 <b>Price:</b> <b>{effective_unit_price:,} ETB</b>{price_mod_display}\n"
            f"📂 <b>Category:</b> {pcat}\n"
            f"⭐ <b>Rating:</b> {rating_display}\n"
            f"🎨 <b>Selected Finish:</b> <b>{scolor}</b>{size_display}\n"
            f"📊 <b>Availability:</b> {stock_badge}\n"
            f"{engraving_status}\n\n"
            f"📝 <b>Description:</b>\n"
            f"{pdesc}\n\n"
            f"✨ <i>Select options below to view real-time photo &amp; stock:</i>"
        )

        keyboard = []

        # Color Selection Row
        colors = list(dict.fromkeys(v.finish_name for v in variants if v.finish_name))
        if len(colors) > 1:
            color_row = []
            for c_name in colors:
                v_match = next((v for v in variants if v.finish_name == c_name and (not selected_size or v.size_name == selected_size)), None)
                if not v_match:
                    v_match = next((v for v in variants if v.finish_name == c_name), None)
                lbl = f"✓ {c_name}" if c_name == selected_color else f"{c_name}"
                if v_match:
                    color_row.append(InlineKeyboardButton(lbl, callback_data=f"selvar_{product.id}_{v_match.id}"))
            keyboard.append(color_row)

        # Size Selection Row
        sizes = list(dict.fromkeys(v.size_name for v in variants if v.size_name))
        if sizes:
            size_row = []
            for s_name in sizes:
                v_match = next((v for v in variants if v.size_name == s_name and (not selected_color or v.finish_name == selected_color)), None)
                if not v_match:
                    v_match = next((v for v in variants if v.size_name == s_name), None)
                lbl = f"✓ {s_name}" if s_name == selected_size else f"{s_name}"
                if v_match:
                    size_row.append(InlineKeyboardButton(lbl, callback_data=f"selvar_{product.id}_{v_match.id}"))
            keyboard.append(size_row)

        # Engraving Action Row
        if engraving_selected:
            keyboard.append([InlineKeyboardButton("✍️ Edit Custom Engraving", callback_data=f"engrave_{product.id}"),
                             InlineKeyboardButton("❌ Remove Engraving", callback_data=f"clear_engrave_{product.id}")])
        else:
            keyboard.append([InlineKeyboardButton("✍️ Add Custom Wood Engraving (+400 ETB)", callback_data=f"engrave_{product.id}")])

        # Add to Cart / Buy Now Row
        if sel_variant.stock_quantity > 0:
            keyboard.append([
                InlineKeyboardButton("🛒 Add to Cart", callback_data=f"addcart_{product.id}_{sel_variant.id}"),
                InlineKeyboardButton("⚡ Buy Now", callback_data=f"buynow_{product.id}_{sel_variant.id}")
            ])
        else:
            keyboard.append([InlineKeyboardButton("🔔 Notify When In Stock", callback_data=f"notify_stock_{product.id}")])

        keyboard.append([
            InlineKeyboardButton("🛒 View Cart", callback_data="view_cart"),
            InlineKeyboardButton("🔙 Back to Catalog", callback_data="catalog")
        ])

        prev_image = context.user_data.get(f"active_img_{product.id}")
        context.user_data[f"active_img_{product.id}"] = active_image

        chat_id = update.effective_chat.id

        if active_image:
            if query and query.message and query.message.photo and prev_image == active_image:
                try:
                    await query.edit_message_caption(
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
                    return
                except Exception:
                    pass

            if query and query.message:
                try:
                    await query.message.delete()
                except Exception:
                    pass

            if os.path.exists(active_image):
                with open(active_image, 'rb') as photo_file:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_file,
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
            else:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=active_image,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
        else:
            await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        db.close()
