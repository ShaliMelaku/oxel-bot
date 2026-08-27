import os
import csv
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, Order, User, Product, ProductVariant


def export_orders_csv(db: Session) -> str:
    """Export all orders to a structured CSV file."""
    os.makedirs('data/exports', exist_ok=True)
    filename = f"data/exports/Oxel_Orders_{datetime.now().strftime('%Y_%m_%d')}.csv"

    orders = db.query(Order).order_by(Order.created_at.desc()).all()

    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Order Number', 'Date', 'User ID', 'Customer Phone', 'Status',
            'Payment Method', 'Payment Ref', 'Subtotal (ETB)', 'Discount (ETB)',
            'Shipping Fee (ETB)', 'Total Price (ETB)', 'Shipping Address', 'Delivery Slot'
        ])

        for o in orders:
            writer.writerow([
                o.order_number,
                o.created_at.strftime('%Y-%m-%d %H:%M') if o.created_at else '',
                o.user_id,
                o.phone or '',
                o.status,
                o.payment_method or '',
                o.payment_reference or '',
                o.subtotal or 0,
                o.discount_amount or 0,
                o.shipping_fee or 0,
                o.total_price or 0,
                o.shipping_address or '',
                o.delivery_slot or ''
            ])

    return filename


def export_customers_csv(db: Session) -> str:
    """Export all customers & VIP tiers to a CSV file."""
    os.makedirs('data/exports', exist_ok=True)
    filename = f"data/exports/Oxel_Customers_{datetime.now().strftime('%Y_%m_%d')}.csv"

    users = db.query(User).order_by(User.created_at.desc()).all()

    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'User ID', 'Username', 'First Name', 'Last Name', 'Phone',
            'VIP Tier', 'Loyalty Points', 'Joined Date'
        ])

        for u in users:
            writer.writerow([
                u.user_id,
                u.username or '',
                u.first_name or '',
                u.last_name or '',
                u.phone or '',
                u.vip_tier or 'Bronze',
                u.loyalty_points or 0,
                u.created_at.strftime('%Y-%m-%d') if u.created_at else ''
            ])

    return filename


def export_inventory_csv(db: Session) -> str:
    """Export all products and variants inventory to a CSV file."""
    os.makedirs('data/exports', exist_ok=True)
    filename = f"data/exports/Oxel_Inventory_{datetime.now().strftime('%Y_%m_%d')}.csv"

    products = db.query(Product).all()

    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Product ID', 'Product Name', 'Category', 'Base Price (ETB)',
            'In Stock', 'Variant Finish', 'Size', 'Stock Quantity', 'Price Modifier (ETB)'
        ])

        for p in products:
            if p.variants:
                for v in p.variants:
                    writer.writerow([
                        p.id, p.name, p.category or 'Accessory', p.price,
                        'YES' if p.in_stock else 'NO', v.finish_name,
                        v.size_name or 'Standard', v.stock_quantity, v.price_modifier or 0
                    ])
            else:
                writer.writerow([
                    p.id, p.name, p.category or 'Accessory', p.price,
                    'YES' if p.in_stock else 'NO', 'Standard', 'Standard', 10, 0
                ])

    return filename
