import logging
from sqlalchemy.orm import Session
from database import Product, ProductVariant

logger = logging.getLogger(__name__)


def check_stock_availability(db: Session, product_id: int, variant_id: int = None, quantity: int = 1) -> bool:
    """Check if requested quantity is available in stock for a product/variant."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or not product.in_stock:
        return False

    if variant_id:
        variant = db.query(ProductVariant).filter(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
            ProductVariant.is_active == True
        ).first()
        if not variant or variant.stock_quantity < quantity:
            return False
    return True


def deduct_stock_atomic(db: Session, product_id: int, variant_id: int = None, quantity: int = 1) -> bool:
    """
    Atomically deduct stock for a product variant (or update product availability).
    Uses database row locking (`with_for_update`) where supported to prevent race conditions.
    Returns True if deduction succeeded, False if insufficient stock.
    """
    # Guard against invalid quantity values before any DB access
    if not isinstance(quantity, int) or quantity <= 0 or quantity > 9999:
        logger.warning(f"Stock deduction rejected: invalid quantity={quantity} for product {product_id}")
        return False

    try:
        product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
        if not product or not product.in_stock:
            logger.warning(f"Stock deduction failed: Product {product_id} out of stock or inactive")
            return False

        if variant_id:
            variant = db.query(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product_id
            ).with_for_update().first()

            if not variant or variant.stock_quantity < quantity:
                logger.warning(f"Stock deduction failed: Variant {variant_id} requested {quantity}, available {variant.stock_quantity if variant else 0}")
                return False

            variant.stock_quantity -= quantity
            if variant.stock_quantity <= 0:
                variant.stock_quantity = 0

            # Update overall product in_stock if all variants are out of stock
            total_remaining = sum(v.stock_quantity for v in product.variants)
            if total_remaining <= 0:
                product.in_stock = False

        return True
    except Exception as e:
        logger.exception(f"Error executing atomic stock deduction for product {product_id}, variant {variant_id}")
        return False


def restore_stock_atomic(db: Session, product_id: int, variant_id: int = None, quantity: int = 1) -> bool:
    """Restore stock for cancelled/rejected orders."""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            product.in_stock = True

        if variant_id:
            variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
            if variant:
                variant.stock_quantity += quantity
        return True
    except Exception:
        logger.exception("Error restoring stock")
        return False
