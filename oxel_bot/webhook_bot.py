"""
webhook_bot.py — Oxel Bot in Webhook Mode (PythonAnywhere Free Plan)
=====================================================================
Uses asyncio.run() with PTB async context manager per request.
Compatible with PythonAnywhere WSGI server.
"""

import asyncio
import logging
import os
import sys

# ── Path setup (must be first) ─────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

# ── Load .env ──────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from config import BOT_TOKEN
from database import create_tables, seed_products

# ── Handler imports ────────────────────────────────────────────────────────────
from handlers.start import start_command, help_command, about_command
from handlers.catalog import catalog_command, show_category, show_product_detail
from handlers.cart import (
    add_to_cart, view_cart, prompt_clear_cart, clear_cart,
    clear_cart_command, update_cart_handler, adjust_quantity
)
from handlers.checkout import checkout, process_address, process_phone, confirm_address
from handlers.payment import (
    payment_instructions, upload_receipt, process_receipt,
    process_reference, place_order, pay_with_points_handler,
    reenter_payment_info_handler
)
from handlers.tracking import track_order, process_tracking, show_order_status, my_orders
from handlers.admin import (
    admin_panel, admin_orders, admin_manage_order,
    admin_gen_label_callback, admin_ship_order_callback,
    admin_pending, admin_inventory, admin_products, admin_promos,
    cms_toggle_promo, admin_crm, admin_routes,
    admin_broadcast_menu, broadcast_set_target,
    broadcast_stage_message, broadcast_confirm_send,
    cms_add_new_product, cms_confirm_delete, cms_delete_product,
    verify_order, reject_order,
    status_command, ship_command, broadcast_command, setstock_command,
    addproduct_command, addpromo_command, cms_edit_product,
    cms_toggle_stock, cms_add_stock,
    givepoints_command, userinfo_command, bulkship_command,
    broadcast_vip_command, shipping_label_command,
    confirm_delivery_command, admin_confirm_delivery_callback,
    admin_promo_wizard_start, admin_promo_wizard_callback,
    admin_prompt_deliv_code_callback
)
from handlers.loyalty import loyalty_menu, redeem_points_for_discount
from handlers.profile import user_profile_menu
from handlers.reviews import prompt_order_rating, process_rating
from handlers.bundle import (
    show_bundle_detail, bundle_start_wizard, bundle_color_step,
    bundle_back_step, bundle_confirm, bundle_add_to_cart
)
from bot import handle_callback, handle_message


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await show_order_status(update, context, context.args[0].upper())
    else:
        await track_order(update, context)


# ── Database ───────────────────────────────────────────────────────────────────
logger.info("Initialising database...")
create_tables()
seed_products()
logger.info("Database ready.")


def _build_ptb_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('about', about_command))
    app.add_handler(CommandHandler('catalog', catalog_command))
    app.add_handler(CommandHandler('cart', view_cart))
    app.add_handler(CommandHandler('clearcart', clear_cart_command))
    app.add_handler(CommandHandler('track', track_command))
    app.add_handler(CommandHandler('orders', my_orders))
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

    # Callback & message handlers
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.LOCATION, handle_message))
    app.add_handler(MessageHandler(filters.CONTACT, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    app.add_handler(MessageHandler(filters.VIDEO, handle_message))
    app.add_handler(MessageHandler(filters.AUDIO, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_message))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_message))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


ptb_app: Application = _build_ptb_app()


# ── Flask Web App ──────────────────────────────────────────────────────────────
flask_app = Flask(__name__)


async def _process_update(json_data: dict):
    async with ptb_app:
        update = Update.de_json(json_data, ptb_app.bot)
        await ptb_app.process_update(update)


@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Receive Telegram update and process it via asyncio.run."""
    json_data = request.get_json(force=True)
    if not json_data:
        return 'Bad Request', 400

    try:
        asyncio.run(_process_update(json_data))
    except Exception as exc:
        logger.exception("Error processing update: %s", exc)

    return 'OK', 200


@flask_app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'bot': 'oxel'}), 200


@flask_app.route('/', methods=['GET'])
def index():
    return 'Oxel Bot is running! 🤖', 200


# PythonAnywhere WSGI entry point
application = flask_app

if __name__ == '__main__':
    flask_app.run(debug=False, host='0.0.0.0', port=5000)
