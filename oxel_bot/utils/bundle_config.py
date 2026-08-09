"""
bundle_config.py — Static bundle composition map for Oxel Shop.

Defines which products are included in each bundle, keyed by product slug.
No database migration required — bundles are still Product rows, but their
contents are resolved here at runtime using product slugs.
"""

from typing import List, Dict, Optional

# Maps bundle slug → ordered list of constituent item definitions
BUNDLE_ITEMS: Dict[str, List[Dict]] = {
    "creator-bundle": [
        {"slug": "the-rise",  "label": "The Rise",  "category": "Laptop Stand"},
        {"slug": "the-view",  "label": "The View",  "category": "Phone Holder"},
        {"slug": "the-grip",  "label": "The Grip",  "category": "Controller Holder"},
    ],
    "studio-bundle": [
        {"slug": "the-rise",  "label": "The Rise",  "category": "Laptop Stand"},
        {"slug": "the-view",  "label": "The View",  "category": "Phone Holder"},
        {"slug": "the-grip",  "label": "The Grip",  "category": "Controller Holder"},
        {"slug": "the-shift", "label": "The Shift", "category": "Keyboard Riser"},
        {"slug": "the-base",  "label": "The Base",  "category": "Desk Mat"},
    ],
}

# Bundle savings labels (shown on bundle overview)
BUNDLE_SAVINGS: Dict[str, str] = {
    "creator-bundle": "Save 15% vs individual prices",
    "studio-bundle":  "Save 15% vs individual prices",
}

COLORS = ["Natural Oak", "Dark Walnut", "Midnight Ash"]


def is_bundle(product) -> bool:
    """Return True if the product is a configurable bundle."""
    return product.category == "Bundle" and product.slug in BUNDLE_ITEMS


def get_bundle_item_defs(slug: str) -> List[Dict]:
    """Return the list of item definitions for a bundle slug."""
    return BUNDLE_ITEMS.get(slug, [])


def get_bundle_items_with_products(slug: str, db) -> List[Dict]:
    """
    Resolve bundle item definitions to include actual Product objects.
    Returns list of dicts with keys: slug, label, category, product (or None).
    """
    from database import Product
    items = get_bundle_item_defs(slug)
    result = []
    for item in items:
        product = db.query(Product).filter(Product.slug == item["slug"]).first()
        result.append({**item, "product": product})
    return result


def get_bundle_savings_label(slug: str) -> str:
    return BUNDLE_SAVINGS.get(slug, "Bundle Savings")


def init_bundle_config(bundle_product_id: int, bundle_slug: str, num_items: int) -> Dict:
    """Initialize a fresh bundle_config in context.user_data."""
    return {
        "bundle_product_id": bundle_product_id,
        "bundle_slug": bundle_slug,
        "step": 0,
        "total_steps": num_items,
        "selections": {},  # slug → {"variant_id": int|None, "finish": str}
    }
