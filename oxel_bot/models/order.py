# Order model is defined in database.py
# This module provides order-related helper functions

from datetime import datetime
from database import SessionLocal, Order, OrderStatusHistory, generate_order_number


def create_order(user_id: int, product_id: int, quantity: int, total_price: int,
                 payment_method: str, payment_reference: str, shipping_address: str, notes: str = None):
    """Create a new order and initial status history."""
    db = SessionLocal()
    try:
        order_number = generate_order_number()
        order = Order(
            order_number=order_number,
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            total_price=total_price,
            status='pending',
            payment_method=payment_method,
            payment_reference=payment_reference,
            shipping_address=shipping_address,
            notes=notes or f"Payment reference: {payment_reference}"
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        history = OrderStatusHistory(
            order_id=order.id,
            status='pending',
            note='Order placed. Awaiting payment verification.'
        )
        db.add(history)
        db.commit()

        return order
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_order_by_number(order_number: str):
    """Get an order by its order number."""
    db = SessionLocal()
    try:
        return db.query(Order).filter(Order.order_number == order_number).first()
    finally:
        db.close()


def get_user_orders(user_id: int, limit: int = 10):
    """Get recent orders for a user."""
    db = SessionLocal()
    try:
        return db.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit).all()
    finally:
        db.close()


def update_order_status(order_id: int, status: str, note: str = None, verified_by: int = None):
    """Update order status and add history entry."""
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None
        order.status = status
        order.updated_at = datetime.now()
        if verified_by:
            order.payment_verified_by = verified_by
        db.commit()

        history = OrderStatusHistory(
            order_id=order.id,
            status=status,
            note=note
        )
        db.add(history)
        db.commit()
        return order
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
