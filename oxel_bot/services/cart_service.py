import logging
from sqlalchemy.orm import Session
from database import Cart, CartItem, Product, ProductVariant
from services.inventory_service import check_stock_availability

logger = logging.getLogger(__name__)


def get_or_create_cart(db: Session, user_id: int) -> Cart:
    """Retrieve or create persistent cart for user."""
    from database import User
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        from models.user import get_or_create_user
        user = get_or_create_user(user_id)

    cart = db.query(Cart).filter(Cart.user_id == user_id).first()
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def add_to_cart(db: Session, user_id: int, product_id: int, variant_id: int = None, quantity: int = 1, customization: str = None) -> CartItem:
    """Add product/variant to user's cart or update existing quantity."""
    cart = get_or_create_cart(db, user_id)
    
    # Check existing item
    item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == product_id,
        CartItem.variant_id == variant_id
    ).first()

    if item:
        item.quantity += quantity
        if customization:
            item.customization = customization
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            variant_id=variant_id,
            quantity=quantity,
            customization=customization
        )
        db.add(item)

    db.commit()
    db.refresh(item)
    return item


def remove_from_cart(db: Session, user_id: int, cart_item_id: int) -> bool:
    """Remove item from user's cart."""
    cart = get_or_create_cart(db, user_id)
    item = db.query(CartItem).filter(CartItem.id == cart_item_id, CartItem.cart_id == cart.id).first()
    if item:
        db.delete(item)
        db.commit()
        return True
    return False


def update_cart_item_quantity(db: Session, user_id: int, cart_item_id: int, quantity: int) -> bool:
    """Update item quantity in cart. If quantity <= 0, remove item."""
    cart = get_or_create_cart(db, user_id)
    item = db.query(CartItem).filter(CartItem.id == cart_item_id, CartItem.cart_id == cart.id).first()
    if not item:
        return False
    
    if quantity <= 0:
        db.delete(item)
    else:
        item.quantity = quantity
    db.commit()
    return True


def clear_cart(db: Session, user_id: int) -> bool:
    """Clear all items from user's cart."""
    cart = db.query(Cart).filter(Cart.user_id == user_id).first()
    if cart:
        db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
        db.commit()
        return True
    return False


def get_cart_summary(db: Session, user_id: int) -> dict:
    """
    Get detailed summary of user's cart including valid/stale stock status, unit prices, and subtotal.
    """
    cart = get_or_create_cart(db, user_id)
    items_data = []
    subtotal = 0
    is_valid = True

    for item in cart.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        variant = db.query(ProductVariant).filter(ProductVariant.id == item.variant_id).first() if item.variant_id else None

        if not product or not product.in_stock:
            stock_ok = False
            is_valid = False
        else:
            stock_ok = check_stock_availability(db, item.product_id, item.variant_id, item.quantity)
            if not stock_ok:
                is_valid = False

        unit_price = product.price if product else 0
        if variant and variant.price_modifier:
            unit_price += variant.price_modifier

        item_subtotal = unit_price * item.quantity
        subtotal += item_subtotal

        items_data.append({
            'cart_item_id': item.id,
            'product_id': item.product_id,
            'product_name': product.name if product else "Unknown Product",
            'variant_id': item.variant_id,
            'finish_name': variant.finish_name if variant else None,
            'size_name': variant.size_name if variant else None,
            'image_url': (variant.image_url if (variant and variant.image_url) else (product.image_url if product else None)),
            'quantity': item.quantity,
            'unit_price': unit_price,
            'subtotal': item_subtotal,
            'customization': item.customization,
            'stock_available': stock_ok
        })

    return {
        'cart_id': cart.id,
        'user_id': user_id,
        'items': items_data,
        'total_items': sum(item['quantity'] for item in items_data),
        'subtotal': subtotal,
        'is_valid_for_checkout': is_valid and len(items_data) > 0
    }
