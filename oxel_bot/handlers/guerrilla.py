import logging
import html
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal, User, Product, ProductVariant
from services.guerrilla_service import (
    get_or_create_slash, apply_slash_click, redeem_hunt_code, redeem_golden_seal
)
from utils.safe_message import safe_edit_text

logger = logging.getLogger(__name__)

# FAQ Knowledge Base & Smart Product Recommendations
FAQ_DATA = {
    'delivery': {
        'title': '🚚 Delivery & Coverage FAQs',
        'text': (
            "🚚 <b>DELIVERY COVERAGE & TIMELINES</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📍 <b>Coverage Area:</b> Expedited delivery across all sub-cities in Addis Ababa (Bole, Kazanchis, Piassa, CMC, Sarbet, Nifas Silk, etc.). Regional shipping available via ETHIO POST / EMS.\n\n"
            "⚡ <b>Delivery Speed:</b>\n"
            "• Same-Day / Next-Day Delivery for standard catalog orders.\n"
            "• 24-48 hours for custom name/logo wood engraving.\n\n"
            "💰 <b>Delivery Fees:</b> Calculated dynamically based on GPS distance from Megenagna workshop (150 - 350 ETB max)."
        ),
        'upsell_product_id': 1
    },
    'wood': {
        'title': '🪵 Wood Care & Timber Selection',
        'text': (
            "🪵 <b>ETHIOPIAN TIMBER & CRAFTSMANSHIP</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌳 <b>Our Woods:</b> Sustainably sourced Ethiopian Wanza (Cordia africana), Natural Oak, and Dark Walnut.\n\n"
            "✨ <b>Finish Choices:</b>\n"
            "• <i>Natural Oak:</i> Bright, Scandinavian aesthetic with warm grain.\n"
            "• <i>Dark Walnut:</i> Executive, deep rich stain for modern setups.\n"
            "• <i>Midnight Ash:</i> Sleek matte black finish.\n\n"
            "🧼 <b>Care Instructions:</b> Wipe gently with a soft micro-fiber cloth. Natural beeswax polish applied before shipping protects against moisture."
        ),
        'upsell_product_id': 2
    },
    'payment': {
        'title': '💳 Payment Methods & Receipts',
        'text': (
            "💳 <b>PAYMENT INSTRUCTIONS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📱 <b>Accepted Methods:</b>\n"
            "• <b>Telebirr:</b> <code>0911000000</code> (Oxel Trading)\n"
            "• <b>CBE (Commercial Bank of Ethiopia):</b> <code>1000123456789</code>\n\n"
            "⚡ <b>How to Verify:</b>\n"
            "1. Transfer the exact order total.\n"
            "2. Upload a screenshot photo of the receipt or type the transaction reference in the bot.\n"
            "3. Admin instantly verifies your order and dispatches courier!"
        ),
        'upsell_product_id': 3
    },
    'engraving': {
        'title': '✍️ Custom Wood Engraving (+400 ETB)',
        'text': (
            "✍️ <b>CUSTOM LASER WOOD ENGRAVING</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✨ Personalize your wooden stand with high-precision laser engraving:\n"
            "• Your Full Name or Monogram\n"
            "• Inspirational Quotes or Motto\n"
            "• Corporate Company Logo (for gifts)\n\n"
            "🎁 <b>VIP Perk:</b> Gold Tier members get FREE custom engraving on all orders!"
        ),
        'upsell_product_id': 1
    }
}


async def guerrilla_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main Guerrilla Marketing & Smart Assistant Hub."""
    text = (
        "🚀 <b>OXEL MARKETING HUB & GUERRILLA CAMPAIGNS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Select an interactive guerrilla offer or support assistant below:\n\n"
        "✂️ <b>Share-to-Slash:</b> Lower product price by sharing with friends!\n"
        "⚡ <b>Trash-the-Plastic Trade-In:</b> Get 500 ETB credit for old plastic stands!\n"
        "🕵️‍♂️ <b>Treasure Hunt:</b> Redeem secret codes for bonus points!\n"
        "🎟️ <b>Golden Ticket:</b> Verify physical unboxing Golden Seal!\n"
        "🔥 <b>Live Reverse Auction:</b> Snatch items on tick-tock price drops!\n"
        "💬 <b>Instant FAQ & Support Assistant:</b> Delivery, Wood & Payments."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✂️ Share-to-Slash Price (/slash)", callback_data="guerrilla_slash_list")],
        [InlineKeyboardButton("⚡ Trash-the-Plastic Trade-In (/tradein)", callback_data="guerrilla_tradein_info")],
        [InlineKeyboardButton("🕵️‍♂️ Treasure Hunt Code (/hunt)", callback_data="guerrilla_hunt_info")],
        [InlineKeyboardButton("🎟️ Golden Seal Unboxing (/goldenticket)", callback_data="guerrilla_golden_info")],
        [InlineKeyboardButton("🔥 Live Tick-Tock Auction (/auction)", callback_data="guerrilla_auction_info")],
        [InlineKeyboardButton("💬 Instant FAQ & Support Assistant", callback_data="faq_menu")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])

    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def faq_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display interactive FAQ menu."""
    text = (
        "💬 <b>OXEL INSTANT FAQ & SUPPORT ASSISTANT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Tap a topic below for instant answers & recommendations:\n"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚚 Delivery Coverage & Timelines", callback_data="faq_topic_delivery")],
        [InlineKeyboardButton("🪵 Wood Care & Timber Selection", callback_data="faq_topic_wood")],
        [InlineKeyboardButton("💳 Payment Methods & Receipt Verification", callback_data="faq_topic_payment")],
        [InlineKeyboardButton("✍️ Custom Wood Engraving Options", callback_data="faq_topic_engraving")],
        [InlineKeyboardButton("🔙 Guerrilla Hub", callback_data="guerrilla_hub")]
    ])
    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def faq_topic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, topic_key: str):
    """Render FAQ topic with smart product upsell recommendation."""
    data = FAQ_DATA.get(topic_key)
    if not data:
        await faq_menu(update, context)
        return

    text = data['text'] + "\n\n💡 <i>Recommended Craft Piece for You:</i>"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 View Recommended Product", callback_data=f"product_{data['upsell_product_id']}")],
        [InlineKeyboardButton("🔙 Back to FAQs", callback_data="faq_menu")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])
    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def slash_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List products available for Share-to-Slash price reduction."""
    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.in_stock == True).limit(6).all()
        text = (
            "✂️ <b>OXEL SHARE-TO-SLASH PRICE ENGINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Select a product below to start slashing its price! Share your slash link with friends on Telegram — each friend who clicks slashes <b>100 ETB off</b> (up to 300 ETB total discount)!\n"
        )
        keyboard = []
        for p in products:
            keyboard.append([InlineKeyboardButton(f"✂️ Slash {p.name} ({p.price:,} ETB)", callback_data=f"slash_prod_{p.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Guerrilla Hub", callback_data="guerrilla_hub")])

        await safe_edit_text(update, context, text, InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        db.close()


async def slash_prod_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    """Render slash details & referral link for a specific product."""
    user = update.effective_user
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return

        slash = get_or_create_slash(db, user.id, product.id)
        bot_username = context.bot.username or "OxelShopBot"
        slash_link = f"https://t.me/{bot_username}?start=slash_{product.id}_{user.id}"

        discount_earned = slash.slash_discount_amount
        slashed_price = max(0, product.price - discount_earned)
        pname = html.escape(product.name)

        text = (
            f"✂️ <b>SHARE-TO-SLASH: {pname}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Original Price: <s>{product.price:,} ETB</s>\n"
            f"🔥 Slashed Price: <b>{slashed_price:,} ETB</b> (Saved -{discount_earned:,} ETB!)\n"
            f"📊 Slashes Received: <b>{slash.slashes_count} / {slash.max_slashes}</b>\n\n"
            f"🔗 <b>Your Exclusive Slash Link:</b>\n"
            f"<code>{html.escape(slash_link)}</code>\n\n"
            f"<b>How to Slash:</b>\n"
            f"Share this link with Telegram friends. Each friend who opens it slashes <b>100 ETB off</b> your price and earns +50 bonus points!"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Buy Now at Slashed Price", callback_data=f"product_{product.id}")],
            [InlineKeyboardButton("🔙 Back to Slash Catalog", callback_data="guerrilla_slash_list")]
        ])

        await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")
    finally:
        db.close()


async def tradein_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Information and photo prompt for Trash-the-Plastic Trade-In Bounty."""
    text = (
        "⚡ <b>TRASH-THE-PLASTIC TRADE-IN BOUNTY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Slogan: <i>Stop using cheap, ugly plastic stands!</i>\n\n"
        "<b>How It Works:</b>\n"
        "1️⃣ Take a photo of your old plastic or metal stand.\n"
        "2️⃣ Send the photo directly to this bot right now!\n"
        "3️⃣ We verify your photo and give you an instant <b>500 ETB Trade-In Credit Code</b> to upgrade to handcrafted Ethiopian Wanza/Oak wood!\n\n"
        "📸 <i>Send your plastic stand photo now to claim your 500 ETB bounty!</i>"
    )
    context.user_data['awaiting_tradein_photo'] = True
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Guerrilla Hub", callback_data="guerrilla_hub")]])
    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def hunt_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Information for Treasure Hunt Codes."""
    text = (
        "🕵️‍♂️ <b>SECRET TREASURE HUNT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Oxel drops hidden secret codes in Telegram photos, PDF catalogs, and social channels!\n\n"
        "<b>Active Hints:</b>\n"
        "🔍 Code #1: Try typing <code>/claim OXELHUNT2026</code>\n"
        "🔍 Code #2: Look closely at page 3 of our PDF Catalog!\n"
        "🔍 Code #3: Check our latest Telegram channel post!\n\n"
        "Type <code>/claim CODE</code> anytime in chat to claim your reward!"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Guerrilla Hub", callback_data="guerrilla_hub")]])
    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def golden_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Information for Golden Seal Unboxing Claim."""
    text = (
        "🎟️ <b>GOLDEN TICKET UNBOXING CLAIM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Every 20th handcrafted piece has a secret <b>Golden Oxel Seal</b> laser-etched underneath its wooden base!\n\n"
        "Did you flip your wooden stand over and find a Golden Seal?\n"
        "Type <code>/goldenticket YOUR_SERIAL_CODE</code> in chat (e.g. <code>/goldenticket GOLDENOXEL</code>) to verify &amp; claim your <b>+2,000 Loyalty Points (200 ETB credit)</b>!"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Guerrilla Hub", callback_data="guerrilla_hub")]])
    await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")


async def auction_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display Tick-Tock Reverse Auction view."""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.in_stock == True).first()
        if not product:
            await safe_edit_text(update, context, "🔥 No active reverse auction right now. Check back Friday at 8 PM!", None)
            return

        # Calculate dynamic auction drop based on current minute
        from datetime import datetime
        now_min = datetime.now().minute
        drop = (now_min % 20) * 50  # drops 50 ETB every minute up to 1000 ETB
        current_auction_price = max(1000, product.price - drop)
        pname = html.escape(product.name)

        text = (
            f"🔥 <b>LIVE TICK-TOCK REVERSE AUCTION</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Item: <b>{pname}</b>\n"
            f"💰 Base Retail Price: <s>{product.price:,} ETB</s>\n"
            f"⚡ Current Live Auction Price: <b>{current_auction_price:,} ETB</b>\n"
            f"⏱️ Price Drops: <b>-50 ETB every 60 seconds!</b>\n\n"
            f"⚠️ <i>The FIRST person to tap SNATCH NOW locks in this piece at the current live price! If you wait too long, someone else will snatch it before you!</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ SNATCH NOW AT {current_auction_price:,} ETB", callback_data=f"product_{product.id}")],
            [InlineKeyboardButton("🔄 Refresh Auction Price", callback_data="guerrilla_auction_info")],
            [InlineKeyboardButton("🔙 Guerrilla Hub", callback_data="guerrilla_hub")]
        ])

        await safe_edit_text(update, context, text, keyboard, parse_mode="HTML")
    finally:
        db.close()
