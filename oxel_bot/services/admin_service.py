import logging
from sqlalchemy.orm import Session
from database import AdminAuditLog, Product, ProductVariant, User, Order
from services.loyalty_service import award_points

logger = logging.getLogger(__name__)


def log_admin_action(db: Session, admin_id: int, action: str, target_type: str, target_id: str = None, details: str = None):
    """Log admin action to audit log database table."""
    audit_entry = AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        details=details
    )
    db.add(audit_entry)
    db.commit()


def add_product_variant(
    db: Session,
    admin_id: int,
    product_id: int,
    finish_name: str,
    stock_quantity: int = 10,
    price_modifier: int = 0,
    size_name: str = None,
    image_url: str = None
) -> ProductVariant:
    """Add new variant to product with customizable finish, size, price, photo, and admin audit log."""
    variant = ProductVariant(
        product_id=product_id,
        finish_name=finish_name,
        size_name=size_name,
        image_url=image_url,
        stock_quantity=stock_quantity,
        price_modifier=price_modifier
    )
    db.add(variant)
    db.commit()

    log_admin_action(db, admin_id, 'ADD_VARIANT', 'ProductVariant', variant.id, f"Added variant '{finish_name}' (size: {size_name or 'Default'}) to product #{product_id}")
    return variant


def update_variant_stock(db: Session, admin_id: int, variant_id: int, new_stock: int) -> ProductVariant:
    """Update stock quantity for variant with admin audit log."""
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if variant:
        old_stock = variant.stock_quantity
        variant.stock_quantity = new_stock
        db.commit()
        log_admin_action(db, admin_id, 'UPDATE_STOCK', 'ProductVariant', variant.id, f"Stock updated from {old_stock} to {new_stock}")
    return variant


def update_product_variant_details(
    db: Session,
    admin_id: int,
    variant_id: int,
    finish_name: str = None,
    size_name: str = None,
    price_modifier: int = None,
    image_url: str = None
) -> ProductVariant:
    """Update custom variant attributes (finish, size, price_modifier, image_url) with admin audit log."""
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if variant:
        if finish_name is not None:
            variant.finish_name = finish_name
        if size_name is not None:
            variant.size_name = size_name
        if price_modifier is not None:
            variant.price_modifier = price_modifier
        if image_url is not None:
            variant.image_url = image_url
        db.commit()
        log_admin_action(db, admin_id, 'UPDATE_VARIANT', 'ProductVariant', variant.id, f"Updated variant attributes for #{variant.id}")
    return variant


def adjust_user_loyalty(db: Session, admin_id: int, user_id: int, points: int, reason: str) -> bool:
    """Manually adjust user's loyalty points with admin audit log."""
    success = award_points(
        db,
        user_id=user_id,
        points=points,
        trans_type='admin_adjustment',
        description=f"Admin adjustment by #{admin_id}: {reason}"
    )
    if success:
        log_admin_action(db, admin_id, 'LOYALTY_ADJUSTMENT', 'User', user_id, f"Adjusted {points} pts. Reason: {reason}")
    return success
