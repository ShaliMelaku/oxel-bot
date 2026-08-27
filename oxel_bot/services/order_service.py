import logging
import re
from datetime import datetime
from sqlalchemy.orm import Session
from database import Order, OrderItem, OrderStatusHistory, generate_order_number, generate_delivery_code
from services.cart_service import get_cart_summary, clear_cart
from services.promo_service import validate_promo_code, record_promo_usage
from services.inventory_service import deduct_stock_atomic, restore_stock_atomic

logger = logging.getLogger(__name__)

_ALLOWED_PAYMENT_METHODS = {
    'Chapa', 'TeleBirr', 'Telebirr', 'telebirr',
    'CBE', 'cbe', 'Bank Transfer',
    'LOYALTY_POINTS', 'cash', 'Cash on Delivery'
}
_PHONE_RE = re.compile(r'^\+?[0-9]{7,15}$')


def _sanitize_str(value: str, max_len: int, field_name: str) -> str:
    """Strip whitespace and enforce max length on text fields."""
    if not value:
        return value
    value = value.strip()
    if len(value) > max_len:
        logger.warning(f"Input truncated: {field_name} exceeded {max_len} chars (got {len(value)})")
        value = value[:max_len]
    return value


def create_order_from_cart(
    db: Session,
    user_id: int,
    payment_method: str = "Chapa",
    shipping_address: str = None,
    delivery_slot: str = None,
    phone: str = None,
    promo_code: str = None,
    engraving_text: str = None,
    notes: str = None,
    latitude: float = None,
    longitude: float = None,
    shipping_fee: int = None
) -> Order:
    """
    Convert user's persistent cart into a multi-item Order with frozen unit prices,
    atomic stock deduction, dynamic distance delivery fee calculation, and server-side pricing validation.
    """
    # ── Input validation ───────────────────────────────────────────────────
    if payment_method and payment_method not in _ALLOWED_PAYMENT_METHODS:
        raise ValueError(f"Invalid payment method: '{payment_method}'.")

    if phone:
        phone_clean = re.sub(r'[\s\-]', '', phone.strip())
        if not _PHONE_RE.match(phone_clean):
            raise ValueError(f"Invalid phone number format: '{phone}'.")
        phone = phone_clean

    if shipping_address:
        shipping_address = _sanitize_str(shipping_address, 500, 'shipping_address')
    if engraving_text:
        engraving_text = _sanitize_str(engraving_text, 200, 'engraving_text')
    if notes:
        notes = _sanitize_str(notes, 1000, 'notes')
    if promo_code:
        promo_code = _sanitize_str(promo_code, 50, 'promo_code')

    cart_summary = get_cart_summary(db, user_id)
    if not cart_summary['is_valid_for_checkout']:
        raise ValueError("Cart is empty or contains out-of-stock items.")

    subtotal = cart_summary['subtotal']
    discount_amount = 0

    # Validate promo code server-side if provided
    if promo_code:
        cart_product_ids = [item['product_id'] for item in cart_summary['items']]
        promo_res = validate_promo_code(db, promo_code, user_id, subtotal, cart_product_ids=cart_product_ids)
        if promo_res['valid']:
            discount_amount = promo_res['discount_amount']
            record_promo_usage(db, promo_code)
        else:
            logger.warning(f"Promo code '{promo_code}' invalid for user {user_id}: {promo_res['message']}")

    # Calculate dynamic delivery fee based on radius from Megenagna, Addis Ababa
    if shipping_fee is None:
        from utils.geo import calculate_delivery_fee
        shipping_fee, _ = calculate_delivery_fee(latitude, longitude)

    engraving_fee = 0
    total_price = max(0, subtotal - discount_amount + shipping_fee)

    # 1. Atomically deduct stock for all items
    deducted_items = []
    for item in cart_summary['items']:
        success = deduct_stock_atomic(db, item['product_id'], item['variant_id'], item['quantity'])
        if not success:
            # Rollback previously deducted items if any item fails
            for d_prod, d_var, d_qty in deducted_items:
                restore_stock_atomic(db, d_prod, d_var, d_qty)
            raise ValueError(f"Insufficient stock for product '{item['product_name']}'. Checkout cancelled.")
        deducted_items.append((item['product_id'], item['variant_id'], item['quantity']))

    # 2. Create Order
    order_number = generate_order_number()
    delivery_code = generate_delivery_code()
    first_item = cart_summary['items'][0] if cart_summary['items'] else None

    order = Order(
        order_number=order_number,
        delivery_code=delivery_code,
        user_id=user_id,
        subtotal=subtotal,
        discount_amount=discount_amount,
        shipping_fee=shipping_fee,
        engraving_fee=engraving_fee,
        total_price=total_price,
        status='pending',
        payment_method=payment_method,
        phone=phone,
        shipping_address=shipping_address,
        delivery_slot=delivery_slot,
        latitude=latitude,
        longitude=longitude,
        promo_code=promo_code if discount_amount > 0 else None,
        notes=notes,
        # Legacy single-item columns populated from first item for backward compatibility
        product_id=first_item['product_id'] if first_item else None,
        finish_variant=first_item['finish_name'] if first_item else None,
        quantity=first_item['quantity'] if first_item else 1
    )
    db.add(order)
    db.flush()

    # 3. Create OrderItems with frozen unit prices
    for item in cart_summary['items']:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item['product_id'],
            variant_id=item['variant_id'],
            product_name=item['product_name'],
            finish_variant=item['finish_name'],
            unit_price=item['unit_price'],
            quantity=item['quantity'],
            subtotal=item['subtotal'],
            engraving_text=engraving_text if item == cart_summary['items'][0] else None
        )
        db.add(order_item)

    # 4. Status history
    history = OrderStatusHistory(
        order_id=order.id,
        status='pending',
        note='Multi-item order created. Pending payment.'
    )
    db.add(history)

    # 5. Clear cart
    clear_cart(db, user_id)

    db.commit()
    db.refresh(order)
    logger.info(f"Order #{order_number} created successfully for user {user_id}")
    return order


def update_order_status(db: Session, order_id: int, new_status: str, note: str = None, admin_id: int = None) -> Order:
    """Update order status with audit log, handle stock restock and points refund on cancellation/refund."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None

    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.now()

    if admin_id and new_status in ['verified', 'confirmed']:
        order.payment_verified_by = admin_id

    # If cancelling, refunding, or rejecting, restore inventory stock & refund loyalty points
    if new_status in ['cancelled', 'refunded', 'rejected', 'failed'] and old_status not in ['cancelled', 'refunded', 'rejected', 'failed']:
        for item in order.items:
            restore_stock_atomic(db, item.product_id, item.variant_id, item.quantity)

        # Refund loyalty points if order was paid via LOYALTY_POINTS
        if order.payment_method == 'LOYALTY_POINTS':
            from database import User
            user = db.query(User).filter(User.user_id == order.user_id).first()
            if user:
                user.loyalty_points = (user.loyalty_points or 0) + int(order.total_price)
                logger.info(f"Refunded {order.total_price} loyalty points to user #{order.user_id} for order #{order.order_number} (status: {new_status})")

    history = OrderStatusHistory(
        order_id=order.id,
        status=new_status,
        note=note or f"Status changed from {old_status} to {new_status}"
    )
    db.add(history)
    db.commit()
    return order


def confirm_order_delivery(db: Session, order_identifier: str, input_code: str, admin_id: int = None) -> tuple[bool, str, Order]:
    """
    Validate customer's 6-digit delivery confirmation code given to delivery admin.
    If valid, transitions order status to 'delivered' / fulfilled.
    """
    from database import User
    from services.loyalty_service import award_points

    query = db.query(Order)
    if isinstance(order_identifier, int) or (isinstance(order_identifier, str) and order_identifier.isdigit()):
        order = query.filter(Order.id == int(order_identifier)).first()
    else:
        order = query.filter(Order.order_number == str(order_identifier).strip().upper()).first()

    if not order:
        return False, "Order not found.", None

    if not order.delivery_code:
        # Fallback for old orders: auto-assign delivery code
        order.delivery_code = generate_delivery_code()
        db.commit()

    if str(order.delivery_code).strip() != str(input_code).strip():
        logger.warning(f"Delivery code mismatch for order #{order.order_number}: provided '{input_code}', expected '{order.delivery_code}'")
        return False, f"❌ Invalid delivery confirmation code '{input_code}'. Package hand-off denied.", order

    # Valid code -> Fulfill order
    update_order_status(db, order.id, 'delivered', f"Delivery verified with customer code '{input_code}'", admin_id)

    # Award customer loyalty points upon successful delivery fulfillment
    points_earned = int(order.total_price * 0.05)
    award_points(db, order.user_id, points_earned, trans_type='order_reward', description=f"Reward for Order #{order.order_number}", order_id=order.id)

    logger.info(f"Order #{order.order_number} successfully fulfilled & delivered via customer confirmation code.")
    return True, f"✅ Delivery code verified! Order #{order.order_number} is now fully DELIVERED & FULFILLED.", order


def get_shipping_label_data(db: Session, order_identifier: str) -> dict:
    """Build structured dictionary for generating package shipping label PDF."""
    from database import User, Product
    query = db.query(Order)
    if isinstance(order_identifier, int) or (isinstance(order_identifier, str) and order_identifier.isdigit()):
        order = query.filter(Order.id == int(order_identifier)).first()
    else:
        order = query.filter(Order.order_number == str(order_identifier).strip().upper()).first()

    if not order:
        return None

    if not order.delivery_code:
        order.delivery_code = generate_delivery_code()
        db.commit()

    customer = db.query(User).filter(User.user_id == order.user_id).first()
    cust_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip() if customer else "Valued Customer"
    cust_phone = order.phone or (customer.phone if customer else None) or "N/A"

    items_list = []
    if order.items:
        for item in order.items:
            items_list.append({
                'name': item.product_name,
                'finish': item.finish_variant or 'Standard',
                'quantity': item.quantity,
                'price': item.unit_price,
                'engraving': item.engraving_text
            })
    else:
        product = db.query(Product).filter(Product.id == order.product_id).first()
        items_list.append({
            'name': product.name if product else 'Wooden Product',
            'finish': order.finish_variant or 'Standard',
            'quantity': order.quantity or 1,
            'price': order.total_price,
            'engraving': None
        })

    return {
        'order_number': order.order_number,
        'delivery_code': order.delivery_code,
        'customer_name': cust_name,
        'phone': cust_phone,
        'shipping_address': order.shipping_address or 'Addis Ababa, Ethiopia',
        'delivery_slot': order.delivery_slot or 'Standard Delivery',
        'items': items_list,
        'subtotal': order.subtotal or 0,
        'discount_amount': order.discount_amount or 0,
        'shipping_fee': order.shipping_fee or 0,
        'engraving_fee': order.engraving_fee or 0,
        'total_price': order.total_price or 0,
        'date': order.created_at.strftime('%b %d, %Y')
    }
