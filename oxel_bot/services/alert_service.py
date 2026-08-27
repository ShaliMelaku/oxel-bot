import logging
import html
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import StockAlert, Product, User

logger = logging.getLogger(__name__)


def subscribe_alert(db: Session, user_id: int, product_id: int, alert_type: str = 'restock', target_price: int = None) -> tuple[bool, str]:
    """Subscribe a user to restock or price drop alerts for a product."""
    existing = db.query(StockAlert).filter(
        StockAlert.user_id == user_id,
        StockAlert.product_id == product_id,
        StockAlert.alert_type == alert_type,
        StockAlert.is_active == True
    ).first()

    if existing:
        return False, "🔔 You are already subscribed to alerts for this piece!"

    alert = StockAlert(
        user_id=user_id,
        product_id=product_id,
        alert_type=alert_type,
        target_price=target_price,
        is_active=True
    )
    db.add(alert)
    db.commit()

    label = "Restock" if alert_type == 'restock' else "Price Drop"
    return True, f"🔔 <b>{label} Alert Activated!</b>\nWe will instantly notify you on Telegram when this piece is restocked / drops in price."


async def trigger_restock_notifications(bot, db: Session, product_id: int):
    """Send Telegram notifications to all users waiting for a restock of product_id."""
    alerts = db.query(StockAlert).filter(
        StockAlert.product_id == product_id,
        StockAlert.alert_type == 'restock',
        StockAlert.is_active == True
    ).all()

    if not alerts:
        return

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return

    pname = html.escape(product.name)
    text = (
        f"🎉 <b>RESTOCK ALERT — BACK IN STOCK!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Good news! The piece you've been eyeing is back in stock:\n\n"
        f"📦 <b>{pname}</b>\n"
        f"💰 Price: <b>{product.price:,} ETB</b>\n"
        f"⭐ Rating: {product.avg_rating} ({product.review_count} reviews)\n\n"
        f"Tap below to view details and place your order before it sells out again! 🏃💨"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 View Product", callback_data=f"product_{product.id}")],
        [InlineKeyboardButton("📦 Browse Catalog", callback_data="catalog")]
    ])

    sent_count = 0
    for alert in alerts:
        try:
            await bot.send_message(
                chat_id=alert.user_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            alert.is_active = False  # Deactivate alert after notifying
            sent_count += 1
        except Exception as e:
            logger.warning(f"Could not send restock alert to user {alert.user_id}: {e}")

    db.commit()
    logger.info(f"Triggered {sent_count} restock notifications for product '{product.name}' (ID #{product.id}).")


async def trigger_price_drop_notifications(bot, db: Session, product_id: int, old_price: int, new_price: int):
    """Send Telegram notifications to users when product price drops."""
    if new_price >= old_price:
        return

    alerts = db.query(StockAlert).filter(
        StockAlert.product_id == product_id,
        StockAlert.alert_type == 'price_drop',
        StockAlert.is_active == True
    ).all()

    if not alerts:
        return

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return

    savings = old_price - new_price
    pname = html.escape(product.name)
    text = (
        f"📉 <b>PRICE DROP ALERT!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Great news! <b>{pname}</b> just dropped in price!\n\n"
        f"🔥 <b>Was:</b> {old_price:,} ETB → <b>Now: {new_price:,} ETB</b>\n"
        f"🎉 <b>You Save: {savings:,} ETB!</b>\n\n"
        f"Tap below to order now while the special pricing lasts! 🛍️"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 View Product", callback_data=f"product_{product.id}")],
        [InlineKeyboardButton("📦 Browse Catalog", callback_data="catalog")]
    ])

    sent_count = 0
    for alert in alerts:
        try:
            await bot.send_message(
                chat_id=alert.user_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            alert.is_active = False
            sent_count += 1
        except Exception as e:
            logger.warning(f"Could not send price drop alert to user {alert.user_id}: {e}")

    db.commit()
    logger.info(f"Triggered {sent_count} price drop notifications for product '{product.name}' (ID #{product.id}).")
