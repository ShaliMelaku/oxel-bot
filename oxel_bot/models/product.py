# Product model is defined in database.py
# This module provides product-related helper functions

from database import SessionLocal, Product


def get_all_products(in_stock_only: bool = True):
    """Get all products, optionally filtering by stock status."""
    db = SessionLocal()
    try:
        query = db.query(Product)
        if in_stock_only:
            query = query.filter(Product.in_stock == True)
        return query.all()
    finally:
        db.close()


def get_products_by_category(category: str, in_stock_only: bool = True):
    """Get products by category."""
    db = SessionLocal()
    try:
        query = db.query(Product).filter(Product.category == category)
        if in_stock_only:
            query = query.filter(Product.in_stock == True)
        return query.all()
    finally:
        db.close()


def get_product_by_id(product_id: int):
    """Get a single product by ID."""
    db = SessionLocal()
    try:
        return db.query(Product).filter(Product.id == product_id).first()
    finally:
        db.close()
