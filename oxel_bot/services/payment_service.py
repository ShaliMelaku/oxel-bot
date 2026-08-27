import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import Payment, Order, OrderStatusHistory
from services.inventory_service import restore_stock_atomic
from services.loyalty_service import award_points
from services.referral_service import complete_referral_reward

logger = logging.getLogger(__name__)


def create_payment(db: Session, order_id: int, payment_method: str, amount: int, transaction_reference: str = None, receipt_file_id: str = None) -> Payment:
    """Create a new payment record associated with an order."""
    # Check duplicate transaction reference if provided
    if transaction_reference:
        existing = db.query(Payment).filter(
            Payment.transaction_reference == transaction_reference,
            Payment.status.in_(['submitted', 'verified'])
        ).first()
        if existing:
            raise ValueError(f"Transaction reference '{transaction_reference}' has already been submitted.")

    payment = Payment(
        order_id=order_id,
        payment_method=payment_method,
        amount=amount,
        transaction_reference=transaction_reference,
        receipt_file_id=receipt_file_id,
        status='submitted'
    )
    db.add(payment)

    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        order.status = 'submitted'
        history = OrderStatusHistory(
            order_id=order.id,
            status='submitted',
            note=f"Payment submitted via {payment_method}. Ref: {transaction_reference or 'N/A'}"
        )
        db.add(history)

    db.commit()
    db.refresh(payment)
    return payment


def verify_payment(db: Session, payment_id: int, admin_user_id: int) -> bool:
    """Verify payment and mark order as verified/paid."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment or payment.status != 'submitted':
        logger.warning(f"Payment verification failed: Payment {payment_id} not found or not submitted")
        return False

    payment.status = 'verified'
    payment.verified_by = admin_user_id
    payment.verified_at = datetime.now()

    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if order:
        order.status = 'verified'
        history = OrderStatusHistory(
            order_id=order.id,
            status='verified',
            note=f"Payment verified by admin #{admin_user_id}"
        )
        db.add(history)

        # Award loyalty points (1 point per 1 ETB spent) ONLY if not paid via LOYALTY_POINTS
        if payment.payment_method != 'LOYALTY_POINTS' and order.payment_method != 'LOYALTY_POINTS':
            points_earned = int(order.total_price)
            award_points(
                db,
                user_id=order.user_id,
                points=points_earned,
                trans_type='order_reward',
                description=f"Reward for Order #{order.order_number}",
                order_id=order.id
            )

        # Trigger referral completion if applicable
        complete_referral_reward(db, order.user_id)

    db.commit()
    return True


def reject_payment(db: Session, payment_id: int, admin_user_id: int, reason: str) -> bool:
    """Reject payment, update order status, restore inventory stock, and refund loyalty points if applicable."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return False

    payment.status = 'rejected'
    payment.verified_by = admin_user_id
    payment.verified_at = datetime.now()
    payment.rejection_reason = reason

    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if order:
        order.status = 'rejected'
        history = OrderStatusHistory(
            order_id=order.id,
            status='rejected',
            note=f"Payment rejected by admin #{admin_user_id}. Reason: {reason}"
        )
        db.add(history)

        # Restore inventory stock for order items
        for item in order.items:
            restore_stock_atomic(db, item.product_id, item.variant_id, item.quantity)

        # Refund loyalty points if order was paid with LOYALTY_POINTS
        if payment.payment_method == 'LOYALTY_POINTS' or order.payment_method == 'LOYALTY_POINTS':
            from database import User
            user = db.query(User).filter(User.user_id == order.user_id).first()
            if user:
                pts_to_refund = int(payment.amount or order.total_price)
                user.loyalty_points = (user.loyalty_points or 0) + pts_to_refund
                logger.info(f"Refunded {pts_to_refund} loyalty points to user #{order.user_id} due to rejected order #{order.order_number}")

    db.commit()
    return True
