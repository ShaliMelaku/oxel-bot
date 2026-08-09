"""Smart Bundle & Accessory Recommender module."""
from database import SessionLocal, Product


RECOMMENDATION_MAP = {
    'Laptop Stand': ['Phone Holder', 'Desk Mat'],
    'Phone Holder': ['Controller Holder', 'Keyboard Riser'],
    'Controller Holder': ['Phone Holder', 'Desk Mat'],
    'Keyboard Riser': ['Desk Mat', 'Laptop Stand'],
    'Desk Mat': ['Laptop Stand', 'Keyboard Riser']
}


def get_recommendation_for_product(product_id: int) -> dict | None:
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return None

        target_categories = RECOMMENDATION_MAP.get(product.category, ['Desk Mat'])
        rec_prod = db.query(Product).filter(
            Product.category.in_(target_categories),
            Product.id != product_id,
            Product.in_stock == True
        ).first()

        if rec_prod:
            return {
                "id": rec_prod.id,
                "name": rec_prod.name,
                "price": rec_prod.price,
                "category": rec_prod.category
            }
        return None
    finally:
        db.close()
