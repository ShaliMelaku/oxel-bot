from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📦 Browse Products", callback_data="catalog")],
        [InlineKeyboardButton("🛒 My Cart", callback_data="view_cart"),
         InlineKeyboardButton("📋 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("👤 My Profile & VIP", callback_data="user_profile"),
         InlineKeyboardButton("🔍 Track Order", callback_data="track_order")],
        [InlineKeyboardButton("🏅 Loyalty Points", callback_data="loyalty_menu"),
         InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
    ]
    return InlineKeyboardMarkup(keyboard)


def persistent_reply_keyboard():
    """Persistent typing bar area keyboard for standard customer navigation."""
    keyboard = [
        [KeyboardButton("📦 Browse Products"), KeyboardButton("🛒 My Cart")],
        [KeyboardButton("📋 My Orders"), KeyboardButton("👤 Profile & VIP")],
        [KeyboardButton("🏅 Loyalty Points"), KeyboardButton("📞 Contact Support")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def address_input_reply_keyboard(saved_address_1=None, saved_address_2=None):
    """Typing bar area keyboard for address entry at checkout."""
    keyboard = []
    if saved_address_1:
        addr1_lbl = saved_address_1[:32] + ("..." if len(saved_address_1) > 32 else "")
        keyboard.append([KeyboardButton(f"🏠 Primary: {addr1_lbl}")])
    if saved_address_2:
        addr2_lbl = saved_address_2[:32] + ("..." if len(saved_address_2) > 32 else "")
        keyboard.append([KeyboardButton(f"🏢 Secondary: {addr2_lbl}")])
    keyboard.append([KeyboardButton("📍 Share My Location", request_location=True)])
    keyboard.append([KeyboardButton("❌ Cancel Checkout")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def phone_input_reply_keyboard(saved_phone=None):
    """Typing bar area keyboard for phone number collection at checkout."""
    keyboard = []
    if saved_phone:
        keyboard.append([KeyboardButton(f"📱 Use Saved Phone: {saved_phone}")])
    keyboard.append([KeyboardButton("📱 Share Telegram Phone Number", request_contact=True)])
    keyboard.append([KeyboardButton("❌ Cancel Checkout")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def promo_input_reply_keyboard():
    """Typing bar area keyboard for promo code entry."""
    keyboard = [
        [KeyboardButton("🎟️ WELCOME500"), KeyboardButton("🎟️ OXEL10")],
        [KeyboardButton("🏅 MYPOINTS (Redeem Points)")],
        [KeyboardButton("❌ Cancel Promo Entry")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def engraving_input_reply_keyboard():
    """Typing bar area keyboard for wood engraving entry."""
    keyboard = [
        [KeyboardButton("✨ Oxel Studio"), KeyboardButton("✨ Custom Hardwood")],
        [KeyboardButton("❌ Cancel Engraving")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def cancel_reply_keyboard(label: str = "❌ Cancel Input"):
    """Generic single-button cancel reply keyboard."""
    return ReplyKeyboardMarkup([[KeyboardButton(label)]], resize_keyboard=True)


def catalog_keyboard():
    keyboard = [
        [InlineKeyboardButton("💻 Laptop Stands", callback_data="category_laptop"),
         InlineKeyboardButton("📱 Phone Holders", callback_data="category_phone")],
        [InlineKeyboardButton("🎮 Controller Holders", callback_data="category_controller"),
         InlineKeyboardButton("⌨️ Keyboard Risers", callback_data="category_keyboard")],
        [InlineKeyboardButton("🖱️ Desk Mats", callback_data="category_mat"),
         InlineKeyboardButton("🎧 Headphone Stands", callback_data="category_headphone")],
        [InlineKeyboardButton("🎁 Curated Bundles", callback_data="category_bundle"),
         InlineKeyboardButton("📦 All Products", callback_data="category_all")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def order_status_keyboard(order_number: str, is_delivered: bool = False):
    keyboard = []
    if is_delivered:
        keyboard.append([InlineKeyboardButton("⭐ Leave a Review", callback_data=f"prompt_review_{order_number}")])
    keyboard.extend([
        [InlineKeyboardButton("🔄 Refresh Status", callback_data=f"refresh_order_{order_number}")],
        [InlineKeyboardButton("📋 My Orders", callback_data="my_orders"),
         InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("⏳ Pending Verifications", callback_data="admin_pending")],
        [InlineKeyboardButton("📦 All Orders", callback_data="admin_orders")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)
