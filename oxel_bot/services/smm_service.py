import os
import random
import logging
import html
from datetime import datetime
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_CHANNEL, SHOP_NAME
from database import Product, User, Order

logger = logging.getLogger(__name__)

# 4-Pillar Strategic Content Matrix
STRATEGIC_POST_TEMPLATES = {
    'craftsmanship': [
        {
            'headline': "🪵 <b>ETHIOPIAN WANZA & OAK: THE ART OF WOOD CRAFTING</b>",
            'body': (
                "Did you know that natural hardwood actively reduces eye strain and improves focus at work?\n\n"
                "Unlike mass-produced plastic stands that warp and degrade, every Oxel piece is cut from "
                "sustainably harvested Ethiopian Wanza & Natural Oak timber, hand-sanded across 7 precision steps, "
                "and sealed with organic beeswax polish.\n\n"
                "✨ <b>Crafted for longevity. Built for digital creators.</b>"
            ),
            'hashtag': "#OxelCraft #SustainableWood #AddisTech #HandcraftedEthiopia",
            'cta_text': "🪵 Explore Handcrafted Wood Catalog"
        },
        {
            'headline': "🌿 <b>WHY PLASTIC DOESN'T BELONG ON YOUR DESK</b>",
            'body': (
                "Mass-produced plastic desk accessories trap heat, wobble under weight, and look outdated within months.\n\n"
                "Oxel wooden stands are precision-engineered to withstand heavy 16-inch laptops, improve heat ventilation by 40%, "
                "and age gracefully with a rich natural wood patina.\n\n"
                " Upgrade your setup from cheap plastic to luxury Ethiopian hardwood."
            ),
            'hashtag': "#WorkspaceDesign #Ergonomics #MadeInEthiopia #OxelDesk",
            'cta_text': "⚡ Upgrade Your Setup Today"
        }
    ],
    'ergonomics': [
        {
            'headline': "💡 <b>THE 15cm RULE: SAVE YOUR NECK & BACK</b>",
            'body': (
                "Looking down at your laptop screen for 8 hours a day puts <b>over 20kg of extra pressure</b> on your cervical spine.\n\n"
                "Elevating your laptop just 15cm brings your eyes directly to eye level, instantly eliminating neck stiffness, "
                "slouching, and end-of-day fatigue.\n\n"
                " Ergonimic elevation meets timeless wooden aesthetics."
            ),
            'hashtag': "#ErgonomicHealth #RemoteWork #AddisDevelopers #DeskSetup",
            'cta_text': "💻 Find Your Ideal Laptop Elevation"
        },
        {
            'headline': "✨ <b>CLEAN DESK, UNSTOPPABLE MIND</b>",
            'body': (
                "A cluttered desk causes visual friction that reduces your daily focus by up to 28%.\n\n"
                "Organize your workspace with dedicated wooden slots for your phone, controllers, headphones, and laptop. "
                "Transform your workspace into a sleek, camera-ready creative studio.\n\n"
                "🎯 <i>Tools for the Digital Craft.</i>"
            ),
            'hashtag': "#DeskTransformation #ProductivityHacks #OxelStudio",
            'cta_text': "🎁 Browse Desk Bundles & Save 15%"
        }
    ],
    'guerrilla': [
        {
            'headline': "✂️ <b>VIRAL PRICE SLASH IS LIVE!</b>",
            'body': (
                "Want to buy a handcrafted Oxel wooden stand for up to <b>300 ETB OFF</b>?\n\n"
                "Tap below to start a Share-to-Slash deal! Share your slash link with Telegram friends — each friend who taps slashes 100 ETB off your price!\n\n"
                "🔥 <b>Unlimited slashes available today!</b>"
            ),
            'hashtag': "#OxelSlash #TelegramDeals #AddisShopping #GuerrillaDeals",
            'cta_text': "✂️ Start Slashed Price Deal Now"
        },
        {
            'headline': "🕵️‍♂️ <b>HIDDEN TREASURE CODE CHALLENGE!</b>",
            'body': (
                "Attention Oxel Community! We've activated a hidden Secret Treasure Code in our bot today!\n\n"
                "The first 5 users to launch the bot and type <code>/claim OXELHUNT2026</code> win an instant "
                "<b>+500 Loyalty Points (50 ETB credit)</b> directly to their account!\n\n"
                "🏃💨 <i>Fastest fingers win!</i>"
            ),
            'hashtag': "#OxelTreasureHunt #SecretCode #TelegramGames",
            'cta_text': "🕵️‍♂️ Claim Treasure Code in Bot"
        }
    ],
    'social_proof': [
        {
            'headline': "⭐ <b>CUSTOMER HIGHLIGHT: 'BEST DESK UPGRADE IN ADDIS'</b>",
            'body': (
                "<i>'I was skeptical until I opened the box. The Oak finish matches my setup perfectly, and my neck pain from working 10 hours a day is completely gone.'</i>\n"
                " — Henok T., Senior Developer (Addis Ababa)\n\n"
                "⭐ <b>4.9 / 5.0 Average Customer Rating</b> across hundreds of Ethiopian creators and remote workers."
            ),
            'hashtag': "#OxelReviews #CustomerLove #AddisAbaba #Woodworking",
            'cta_text': "⭐ Read Reviews & Shop Catalog"
        }
    ]
}


def generate_strategic_smm_post(db: Session, pillar: str = None) -> tuple[str, InlineKeyboardMarkup, str]:
    """
    Generates a strategic, high-converting SMM channel post based on content pillars.
    Returns: (text, reply_markup, image_url_or_filepath)
    """
    if not pillar or pillar not in STRATEGIC_POST_TEMPLATES:
        pillar = random.choice(list(STRATEGIC_POST_TEMPLATES.keys()))

    template = random.choice(STRATEGIC_POST_TEMPLATES[pillar])
    product = db.query(Product).filter(Product.in_stock == True).order_by(Product.id.desc()).first()

    bot_username = "OxelShopBot"

    text = (
        f"{template['headline']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{template['body']}\n\n"
    )

    if product:
        pname = html.escape(product.name)
        text += (
            f"📦 <b>Featured Piece:</b> {pname}\n"
            f"💰 <b>Price:</b> {product.price:,} ETB\n"
            f"🎨 <b>Finishes:</b> Natural Oak | Dark Walnut | Midnight Ash\n\n"
        )

    text += f"{template['hashtag']}\n📢 Channel: {TELEGRAM_CHANNEL}"

    if pillar == 'guerrilla':
        btn_url = f"https://t.me/{bot_username}?start=guerrilla"
    elif product:
        btn_url = f"https://t.me/{bot_username}?start=prod_{product.id}"
    else:
        btn_url = f"https://t.me/{bot_username}?start=catalog"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(template['cta_text'], url=btn_url)],
        [InlineKeyboardButton("📦 Open Oxel Telegram Shop", url=f"https://t.me/{bot_username}?start=main")]
    ])

    image_path = None
    if product and product.image_url:
        image_path = product.image_url

    return text, keyboard, image_path


async def publish_smm_post_to_channel(bot, db: Session, pillar: str = None) -> tuple[bool, str]:
    """Publish a strategic SMM post directly to @OxelChannel."""
    try:
        text, keyboard, image_path = generate_strategic_smm_post(db, pillar=pillar)

        channel_setting = TELEGRAM_CHANNEL.strip()
        if 't.me/' in channel_setting:
            channel_name = channel_setting.split('t.me/')[-1].strip('/').split('?')[0]
            chat_target = f"@{channel_name}"
        elif not channel_setting.startswith('@'):
            chat_target = f"@{channel_setting}"
        else:
            chat_target = channel_setting

        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                await bot.send_photo(
                    chat_id=chat_target,
                    photo=f,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            await bot.send_message(
                chat_id=chat_target,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        logger.info(f"Successfully published strategic SMM post to channel {chat_target}")
        return True, f"✅ Strategic SMM post published to {chat_target}!"
    except Exception as e:
        logger.error(f"Failed to publish SMM post to channel: {e}")
        return False, f"❌ Channel posting error: {str(e)}"


_last_auto_smm_time = 0


async def check_and_auto_publish_smm(bot, db: Session, interval_seconds: int = 86400):
    """
    Autonomous Scheduler: Checks if 24 hours (86,400s) have passed since the last post.
    If yes, automatically generates and dispatches the next 4-pillar strategic post to @OxelChannel.
    """
    global _last_auto_smm_time
    import time
    now = time.time()
    if _last_auto_smm_time == 0 or (now - _last_auto_smm_time >= interval_seconds):
        _last_auto_smm_time = now
        logger.info("Autonomous SMM Scheduler triggered auto-posting to channel...")
        try:
            await publish_smm_post_to_channel(bot, db)
        except Exception as exc:
            logger.error(f"Autonomous SMM auto-publish error: {exc}")
