import os
from telegram import Update
from telegram.ext import ContextTypes
from config import SHOP_NAME, SHOP_WEBSITE, TELEGRAM_CHANNEL, INSTAGRAM_URL, TIKTOK_URL
from database import SessionLocal, User
from utils.keyboards import main_menu_keyboard
from utils.referral import parse_referral_code, register_referral


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    is_new_user = False
    referrer_id = None
    try:
        from models.user import sync_telegram_user
        existing = sync_telegram_user(db, user)

        # Handle referral deep link if user was newly registered
        if existing and not existing.referred_by:
            args = context.args or []
            ref_arg = args[0] if args else None
            referrer_id = parse_referral_code(ref_arg) if ref_arg else None
            if referrer_id and referrer_id != user.id:
                existing.referred_by = referrer_id
                db.commit()
                register_referral(user.id, referrer_id)
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 <b>REFERRAL ALERT!</b>\n━━━━━━━━━━━━━━━━━━━━\nYour friend <b>{user.first_name}</b> just joined Oxel using your referral link!\n\nYou'll be credited <b>+100 Loyalty Points (100 ETB)</b> the moment they place their first order! 🪵✨",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
    finally:
        db.close()

    welcome_text = f"""✦ *Welcome to {SHOP_NAME}!* ✦
_Tools for the Digital Craft_

Where natural warmth meets digital precision. Premium wooden desk accessories, handcrafted for creators, developers, and digital professionals.

✨ *Available Collections & Finishes:*
• *Natural Oak* · *Dark Walnut* · *Midnight Ash*
• Ergonomic Stands, Holders, Risers & Desk Mats
• 🎁 Save up to *15%* with our curated bundles!

🎁 *REFERRAL REWARD POLICY:*
• Refer a friend & earn *+100 Loyalty Points (100 ETB)* when they place their first order!
• Your friend gets *5% WELCOME DISCOUNT* on their first purchase!
• Tap *🏅 Loyalty Points* below for your personal invite link.

📱 *Connect & Follow {SHOP_NAME}:*
• 📢 Telegram Channel: {TELEGRAM_CHANNEL}
• 📸 Instagram: {INSTAGRAM_URL}
• 🎵 TikTok: {TIKTOK_URL}
• 🌐 Website: {SHOP_WEBSITE}

Tap *📦 Browse Products* below to explore the store!"""

    hero_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'images', 'hero_banner.png')
    hero_path = os.path.abspath(hero_path)

    if update.callback_query:
        query = update.callback_query
        try:
            await query.message.delete()
        except Exception:
            pass

        from utils.keyboards import persistent_reply_keyboard
        if os.path.exists(hero_path):
            with open(hero_path, 'rb') as hero_file:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=hero_file,
                    caption=welcome_text,
                    reply_markup=main_menu_keyboard(),
                    parse_mode="Markdown"
                )
        else:
            await query.message.reply_text(
                welcome_text,
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown"
            )
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="👇 Quick action menu available on your typing bar below:",
            reply_markup=persistent_reply_keyboard()
        )
    else:
        from utils.keyboards import persistent_reply_keyboard
        if os.path.exists(hero_path):
            with open(hero_path, 'rb') as hero_file:
                await update.message.reply_photo(
                    photo=hero_file,
                    caption=welcome_text,
                    reply_markup=main_menu_keyboard(),
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                welcome_text,
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown"
            )
        await update.message.reply_text(
            "👇 Quick action menu available on your typing bar below:",
            reply_markup=persistent_reply_keyboard()
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """❓ *Help Center*

*How to Order:*
1️⃣ Browse products from the catalog
2️⃣ Select your preferred Color / Wood Finish
3️⃣ Add items to your cart
4️⃣ Checkout and enter your shipping address
5️⃣ Choose payment method (Telebirr / CBE)
6️⃣ Upload your payment receipt screenshot
7️⃣ Receive official order receipt & track progress!

*Payment Methods:*
💳 Telebirr — Send exact amount
🏦 CBE Mobile — Send exact amount

*Order Tracking:*
Use /track followed by your order number
or tap the "Track Order" button

*Support:*
📬 Contact us via Telegram for fast support!

*Business Hours:*
Mon–Fri: 9:00 AM – 6:00 PM EAT"""

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass
            await update.callback_query.message.reply_text(
                help_text,
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            help_text,
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = """🪵 *About Oxel*

*Oak + Pixel = Oxel*
_Tools for the Digital Craft_

We design and handcraft premium wooden desk accessories for creators, developers, and digital professionals.

Every piece is made from sustainably sourced hardwood, precision-cut and hand-finished to bring warmth and character to your workspace.

🌱 *Sustainably Sourced*
🛠 *Handcrafted with Care*
📐 *Precision Engineered*
🎨 *Camera-Ready Aesthetics*

🇪🇹 Proudly made in Ethiopia."""

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                about_text,
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass
            await update.callback_query.message.reply_text(
                about_text,
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            about_text,
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )
