"""
handlers/bundle.py — Bundle per-item color customization wizard.

Flow:
  1. show_bundle_detail()       — Overview of bundle + items list + Start button
  2. bundle_color_step()        — Per-item color/finish selection (step 1 of N)
  3. bundle_confirm()           — Summary of all selections + Add to Cart button
  4. bundle_add_to_cart()       — Adds each item as a separate CartItem

Callback data patterns (registered in bot.py):
  bundle_start_{bundle_pid}
  bundle_color_{bundle_pid}_{step}_{color_idx}
  bundle_back_{bundle_pid}_{step}
  bundle_confirm_{bundle_pid}
  bundle_addcart_{bundle_pid}
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, Product, ProductVariant
from services.cart_service import add_to_cart as service_add_to_cart, get_cart_summary
from utils.bundle_config import (
    COLORS, get_bundle_items_with_products, get_bundle_savings_label,
    init_bundle_config, is_bundle
)
from utils.safe_message import safe_edit_text

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. BUNDLE OVERVIEW
# ─────────────────────────────────────────────

async def show_bundle_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    """Show the bundle overview page with item list and 'Customize & Add to Cart' CTA."""
    db = SessionLocal()
    try:
        bundle = db.query(Product).filter(Product.id == product_id).first()
        if not bundle:
            await update.callback_query.answer("Bundle not found.", show_alert=True)
            return

        items = get_bundle_items_with_products(bundle.slug, db)
        savings_label = get_bundle_savings_label(bundle.slug)

        items_text = ""
        for i, item in enumerate(items, 1):
            p = item["product"]
            price_str = f" — {p.price:,} ETB" if p else ""
            items_text += f"  {i}. *{item['label']}* _{item['category']}{price_str}_\n"

        text = (
            f"🎁 *{bundle.name}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Bundle Price: {bundle.price:,} ETB*\n"
            f"💡 _{savings_label}_\n\n"
            f"📦 *Included Items ({len(items)}):\n*"
            f"{items_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ *Customize each item's wood finish individually!*\n"
            f"_Tap the button below to choose colors for each piece._"
        )

        keyboard = [
            [InlineKeyboardButton(
                f"🎨 Customize & Add to Cart ({len(items)} items)",
                callback_data=f"bundle_start_{product_id}"
            )],
            [InlineKeyboardButton("🛒 View Cart", callback_data="view_cart")],
            [InlineKeyboardButton("🔙 Back to Catalog", callback_data="catalog")],
        ]

        # Try to show bundle image
        if bundle.image_url:
            import os
            msg = update.callback_query.message
            if msg.photo:
                try:
                    await update.callback_query.edit_message_caption(
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
                    return
                except Exception:
                    pass
            try:
                await msg.delete()
            except Exception:
                pass
            if os.path.exists(bundle.image_url):
                with open(bundle.image_url, 'rb') as f:
                    await context.bot.send_photo(
                        chat_id=msg.chat_id,
                        photo=f,
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
            else:
                await context.bot.send_photo(
                    chat_id=msg.chat_id,
                    photo=bundle.image_url,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        else:
            await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard))
    finally:
        db.close()


# ─────────────────────────────────────────────
# 2. START WIZARD — initialize state & show step 0
# ─────────────────────────────────────────────

async def bundle_start_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE, bundle_product_id: int):
    """Initialize the bundle customization wizard and show step 0."""
    db = SessionLocal()
    try:
        bundle = db.query(Product).filter(Product.id == bundle_product_id).first()
        if not bundle:
            return

        items = get_bundle_items_with_products(bundle.slug, db)
        cfg = init_bundle_config(bundle_product_id, bundle.slug, len(items))
        context.user_data["bundle_config"] = cfg

    finally:
        db.close()

    await _show_color_step(update, context, bundle_product_id, step=0)


# ─────────────────────────────────────────────
# 3. PER-ITEM COLOR SELECTION STEP
# ─────────────────────────────────────────────

async def bundle_color_step(update: Update, context: ContextTypes.DEFAULT_TYPE,
                             bundle_product_id: int, step: int, color_idx: int):
    """Record the color choice for the current step and advance to next."""
    cfg = context.user_data.get("bundle_config")
    if not cfg or cfg["bundle_product_id"] != bundle_product_id:
        await update.callback_query.answer("Session expired. Please start again.", show_alert=True)
        return

    db = SessionLocal()
    try:
        bundle = db.query(Product).filter(Product.id == bundle_product_id).first()
        items = get_bundle_items_with_products(bundle.slug, db)

        if step >= len(items):
            await bundle_confirm(update, context, bundle_product_id)
            return

        item = items[step]
        chosen_finish = COLORS[color_idx] if color_idx < len(COLORS) else COLORS[0]
        product = item["product"]

        # Resolve variant_id for chosen finish
        variant_id = None
        if product:
            v = db.query(ProductVariant).filter(
                ProductVariant.product_id == product.id,
                ProductVariant.finish_name == chosen_finish
            ).first()
            variant_id = v.id if v else None

        cfg["selections"][item["slug"]] = {
            "variant_id": variant_id,
            "finish": chosen_finish,
            "product_id": product.id if product else None,
            "label": item["label"],
        }
        cfg["step"] = step + 1
        context.user_data["bundle_config"] = cfg

    finally:
        db.close()

    # Advance to next step or confirm screen
    next_step = step + 1
    if next_step >= cfg["total_steps"]:
        await bundle_confirm(update, context, bundle_product_id)
    else:
        await _show_color_step(update, context, bundle_product_id, step=next_step)


async def _show_color_step(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            bundle_product_id: int, step: int):
    """Render the color picker for a single bundle item step."""
    cfg = context.user_data.get("bundle_config")
    db = SessionLocal()
    try:
        bundle = db.query(Product).filter(Product.id == bundle_product_id).first()
        items = get_bundle_items_with_products(bundle.slug, db)
        item = items[step]
        product = item["product"]

        total = len(items)

        # Progress summary of already-selected items
        done_lines = ""
        for i in range(step):
            past_item = items[i]
            sel = cfg["selections"].get(past_item["slug"])
            finish_str = sel["finish"] if sel else "—"
            done_lines += f"  ✅ *{past_item['label']}* → {finish_str}\n"

        # Remaining
        remaining_lines = ""
        for i in range(step + 1, total):
            remaining_lines += f"  ⏳ *{items[i]['label']}*\n"

        # Stock info per color
        color_stock = {}
        if product:
            variants = db.query(ProductVariant).filter(
                ProductVariant.product_id == product.id
            ).all()
            color_stock = {v.finish_name: v.stock_quantity for v in variants}

        text = (
            f"🎨 *Choose Finish — Step {step + 1} of {total}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *{item['label']}*\n"
            f"_{item['category']}_\n\n"
        )

        if done_lines:
            text += f"*Chosen so far:*\n{done_lines}\n"

        text += f"👇 *Select wood finish for {item['label']}:*"

        if remaining_lines:
            text += f"\n\n_Still to configure:_\n{remaining_lines}"

        # Color buttons in a single row
        color_buttons = []
        for idx, color in enumerate(COLORS):
            stock = color_stock.get(color, 5)
            stock_tag = "" if stock > 3 else (f" ⚡{stock}" if stock > 0 else " ❌")
            color_buttons.append(InlineKeyboardButton(
                f"{color}{stock_tag}",
                callback_data=f"bundle_color_{bundle_product_id}_{step}_{idx}"
            ))

        keyboard = [
            color_buttons,
        ]

        # Back button
        if step > 0:
            keyboard.append([InlineKeyboardButton(
                "⬅️ Back", callback_data=f"bundle_back_{bundle_product_id}_{step}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"product_{bundle_product_id}")])

    finally:
        db.close()

    await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────
# 4. BACK NAVIGATION
# ─────────────────────────────────────────────

async def bundle_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           bundle_product_id: int, current_step: int):
    """Go back to re-select the previous step's color."""
    cfg = context.user_data.get("bundle_config")
    if not cfg:
        return

    prev_step = current_step - 1
    if prev_step < 0:
        prev_step = 0

    # Remove the previous selection so it can be re-picked
    db = SessionLocal()
    try:
        bundle = db.query(Product).filter(Product.id == bundle_product_id).first()
        items = get_bundle_items_with_products(bundle.slug, db)
        if prev_step < len(items):
            slug_to_clear = items[prev_step]["slug"]
            cfg["selections"].pop(slug_to_clear, None)
            cfg["step"] = prev_step
            context.user_data["bundle_config"] = cfg
    finally:
        db.close()

    await _show_color_step(update, context, bundle_product_id, step=prev_step)


# ─────────────────────────────────────────────
# 5. CONFIRMATION SCREEN
# ─────────────────────────────────────────────

async def bundle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, bundle_product_id: int):
    """Show the final summary of all bundle item selections."""
    cfg = context.user_data.get("bundle_config")
    db = SessionLocal()
    try:
        bundle = db.query(Product).filter(Product.id == bundle_product_id).first()
        items = get_bundle_items_with_products(bundle.slug, db)

        summary_lines = ""
        for item in items:
            sel = cfg["selections"].get(item["slug"])
            finish = sel["finish"] if sel else "Natural Oak"
            summary_lines += f"  ✅ *{item['label']}* → {finish}\n"

        text = (
            f"🎁 *Bundle Customization Summary*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *{bundle.name}*\n\n"
            f"*Your selected finishes:*\n"
            f"{summary_lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Bundle Total: {bundle.price:,} ETB*\n"
            f"💡 _{get_bundle_savings_label(bundle.slug)}_\n\n"
            f"Tap below to add all {len(items)} items to your cart!"
        )

        keyboard = [
            [InlineKeyboardButton(
                f"🛒 Add All {len(items)} Items to Cart",
                callback_data=f"bundle_addcart_{bundle_product_id}"
            )],
            [InlineKeyboardButton(
                "✏️ Edit Selections",
                callback_data=f"bundle_start_{bundle_product_id}"
            )],
            [InlineKeyboardButton("🔙 Back to Bundle", callback_data=f"product_{bundle_product_id}")],
        ]

    finally:
        db.close()

    await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────
# 6. ADD TO CART
# ─────────────────────────────────────────────

async def bundle_add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE, bundle_product_id: int):
    """Add all bundle items as individual CartItems tagged with the bundle name."""
    cfg = context.user_data.get("bundle_config")
    user_id = update.effective_user.id

    db = SessionLocal()
    try:
        bundle = db.query(Product).filter(Product.id == bundle_product_id).first()
        items = get_bundle_items_with_products(bundle.slug, db)

        added = []
        errors = []
        bundle_tag = f"[{bundle.name}]"

        for item in items:
            product = item["product"]
            if not product:
                errors.append(item["label"])
                continue

            sel = cfg.get("selections", {}).get(item["slug"]) if (cfg and isinstance(cfg, dict)) else None
            variant_id = sel["variant_id"] if sel and isinstance(sel, dict) else None
            finish = sel["finish"] if sel and isinstance(sel, dict) else "Natural Oak"

            # If no variant_id resolved, try to find it by finish
            if not variant_id and finish:
                v = db.query(ProductVariant).filter(
                    ProductVariant.product_id == product.id,
                    ProductVariant.finish_name == finish
                ).first()
                variant_id = v.id if v else None

            # Fallback if variant still not found: pick first active variant for product
            if not variant_id:
                v = db.query(ProductVariant).filter(
                    ProductVariant.product_id == product.id
                ).first()
                variant_id = v.id if v else None

            try:
                service_add_to_cart(
                    db,
                    user_id=user_id,
                    product_id=product.id,
                    variant_id=variant_id,
                    quantity=1,
                    customization=bundle_tag
                )
                added.append(f"  ✅ *{item['label']}* — {finish}")
            except Exception as e:
                logger.exception(f"Error adding bundle item {item['slug']} to cart")
                errors.append(item["label"])

        # Calculate cart total
        summary = get_cart_summary(db, user_id)

        # Clear bundle config from session
        context.user_data.pop("bundle_config", None)

        added_text = "\n".join(added) if added else "None"
        error_text = f"\n\n⚠️ *Could not add:* {', '.join(errors)}" if errors else ""

        text = (
            f"🎉 *{bundle.name} Added to Cart!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Items added:*\n"
            f"{added_text}"
            f"{error_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛒 *{summary['total_items']} item(s)* in cart\n"
            f"💰 *Subtotal: {summary['subtotal']:,} ETB*\n\n"
            f"_Bundle items are listed individually in your cart._"
        )

        keyboard = [
            [InlineKeyboardButton("🛒 View Cart", callback_data="view_cart")],
            [InlineKeyboardButton("💳 Checkout Now", callback_data="checkout")],
            [InlineKeyboardButton("📦 Keep Shopping", callback_data="catalog")],
        ]

    finally:
        db.close()

    await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard))
