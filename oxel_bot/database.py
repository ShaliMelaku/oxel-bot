from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime, ForeignKey, Float, func, Index, event
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime, timezone
import uuid
import secrets
import logging
import os
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# ── Engine configuration ───────────────────────────────────────────────────────
db_url = DATABASE_URL
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////") and ":memory:" not in db_url:
    db_filename = db_url.replace("sqlite:///", "")
    project_dir = os.path.dirname(os.path.abspath(__file__))
    abs_db_path = os.path.abspath(os.path.join(project_dir, db_filename))
    db_url = f"sqlite:///{abs_db_path}"

_is_sqlite = 'sqlite' in db_url

if _is_sqlite:
    engine = create_engine(
        db_url,
        connect_args={'check_same_thread': False},
        # SQLite: use WAL journal mode for better concurrent reads without blocking writes
        # pool_pre_ping ensures stale connections are recycled before use
        pool_pre_ping=True,
        pool_recycle=300,     # Recycle connections every 5 minutes
    )
    # Activate WAL mode and recommended SQLite pragmas on every new connection
    @event.listens_for(engine, 'connect')
    def set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')       # Write-Ahead Logging: concurrent readers + writer
        cursor.execute('PRAGMA synchronous=NORMAL;')     # Safe + fast (vs FULL)
        cursor.execute('PRAGMA foreign_keys=ON;')        # Enforce FK integrity
        cursor.execute('PRAGMA cache_size=-64000;')      # 64 MB page cache
        cursor.execute('PRAGMA temp_store=MEMORY;')      # Temp tables in RAM
        cursor.execute('PRAGMA busy_timeout=5000;')      # Wait up to 5s on locked DB
        cursor.close()
else:
    # PostgreSQL / MySQL: proper connection pool
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,           # Maintain 10 persistent connections
        max_overflow=20,        # Allow up to 20 extra connections under spike load
        pool_timeout=30,        # Wait up to 30s for a connection before raising
        pool_recycle=1800,      # Recycle connections every 30 minutes
        pool_pre_ping=True,     # Test connection liveness before using
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    city = Column(String(100))
    sub_city = Column(String(100))
    saved_address_1 = Column(Text, nullable=True)
    saved_address_2 = Column(Text, nullable=True)
    vip_tier = Column(String(50), default="Bronze 🥉")
    loyalty_points = Column(Integer, default=0)
    referred_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    orders = relationship('Order', back_populates='user')
    cart = relationship('Cart', back_populates='user', uselist=False, cascade="all, delete-orphan")
    loyalty_transactions = relationship('LoyaltyTransaction', back_populates='user')


class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(Text)
    category = Column(String(100))
    image_url = Column(String(500))
    in_stock = Column(Boolean, default=True)
    avg_rating = Column(Float, default=5.0)
    review_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    variants = relationship('ProductVariant', back_populates='product', cascade="all, delete-orphan")
    order_items = relationship('OrderItem', back_populates='product')
    cart_items = relationship('CartItem', back_populates='product')


class ProductVariant(Base):
    __tablename__ = 'product_variants'
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    finish_name = Column(String(100), nullable=False)
    size_name = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    stock_quantity = Column(Integer, default=10)
    price_modifier = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    product = relationship('Product', back_populates='variants')
    order_items = relationship('OrderItem', back_populates='variant')
    cart_items = relationship('CartItem', back_populates='variant')


class Cart(Base):
    __tablename__ = 'carts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship('User', back_populates='cart')
    items = relationship('CartItem', back_populates='cart', cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = 'cart_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey('carts.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    variant_id = Column(Integer, ForeignKey('product_variants.id'), nullable=True)
    quantity = Column(Integer, default=1)
    customization = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    cart = relationship('Cart', back_populates='items')
    product = relationship('Product', back_populates='cart_items')
    variant = relationship('ProductVariant', back_populates='cart_items')

    __table_args__ = (
        Index('ix_cart_items_cart_id', 'cart_id'),
        Index('ix_cart_items_product_id', 'product_id'),
    )


class PromoCode(Base):
    __tablename__ = 'promo_codes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    discount_percent = Column(Integer, default=0)
    discount_amount = Column(Integer, default=0)
    start_date = Column(DateTime, nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=True)          # NULL = unlimited (admin sets this)
    current_uses = Column(Integer, default=0)
    per_user_limit = Column(Integer, default=1)        # Default: 1 use per user
    min_order_value = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    # Product restriction: comma-separated product IDs (empty = all products)
    allowed_product_ids = Column(Text, nullable=True)
    # Loyalty tier restriction: 'Bronze 🥉', 'Silver 🥈', 'Gold 🥇' (empty = all tiers)
    min_loyalty_tier = Column(String(50), nullable=True)


class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(20), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    subtotal = Column(Integer, default=0)
    discount_amount = Column(Integer, default=0)
    shipping_fee = Column(Integer, default=0)
    engraving_fee = Column(Integer, default=0)
    total_price = Column(Integer, nullable=False)
    status = Column(String(50), default='pending')
    payment_method = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    shipping_address = Column(Text, nullable=True)
    delivery_slot = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    promo_code = Column(String(50), nullable=True)
    delivery_code = Column(String(20), nullable=True)
    tracking_number = Column(String(100), nullable=True)
    review_rating = Column(Integer, nullable=True)
    review_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Legacy attributes kept for backward compatibility query access
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    finish_variant = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1)
    payment_reference = Column(String(100), nullable=True)
    payment_verified_by = Column(Integer, nullable=True)
    receipt_file_id = Column(String(500), nullable=True)

    user = relationship('User', back_populates='orders')
    items = relationship('OrderItem', back_populates='order', cascade="all, delete-orphan")
    payments = relationship('Payment', back_populates='order', cascade="all, delete-orphan")
    status_history = relationship('OrderStatusHistory', back_populates='order', cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_orders_user_id', 'user_id'),
        Index('ix_orders_status', 'status'),
        Index('ix_orders_order_number', 'order_number'),
        Index('ix_orders_created_at', 'created_at'),
    )


class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    variant_id = Column(Integer, ForeignKey('product_variants.id'), nullable=True)
    product_name = Column(String(100), nullable=False)
    finish_variant = Column(String(100), nullable=True)
    unit_price = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)
    subtotal = Column(Integer, nullable=False)
    engraving_text = Column(String(200), nullable=True)

    order = relationship('Order', back_populates='items')
    product = relationship('Product', back_populates='order_items')
    variant = relationship('ProductVariant', back_populates='order_items')


class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    payment_method = Column(String(50), nullable=False)
    amount = Column(Integer, nullable=False)
    transaction_reference = Column(String(100), nullable=True)
    receipt_file_id = Column(String(500), nullable=True)
    status = Column(String(50), default='pending') # pending, submitted, verified, rejected, failed, refunded, cancelled
    verified_by = Column(Integer, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship('Order', back_populates='payments')


class Referral(Base):
    __tablename__ = 'referrals'
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    referred_user_id = Column(Integer, ForeignKey('users.user_id'), unique=True, nullable=False)
    status = Column(String(50), default='pending') # pending, completed, rejected
    reward_awarded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class LoyaltyTransaction(Base):
    __tablename__ = 'loyalty_transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    points = Column(Integer, nullable=False) # Positive = earned, negative = redeemed
    type = Column(String(50), nullable=False) # order_reward, referral_bonus, discount_redemption, admin_adjustment
    description = Column(String(200), nullable=False)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship('User', back_populates='loyalty_transactions')

    __table_args__ = (
        Index('ix_loyalty_user_id', 'user_id'),
    )


class OrderStatusHistory(Base):
    __tablename__ = 'order_status_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    status = Column(String(50), nullable=False)
    note = Column(String(500))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    order = relationship('Order', back_populates='status_history')


class AdminAuditLog(Base):
    __tablename__ = 'admin_audit_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Admin(Base):
    __tablename__ = 'admins'
    user_id = Column(Integer, primary_key=True)
    role = Column(String(50), default='admin')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class StockAlert(Base):
    __tablename__ = 'stock_alerts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    alert_type = Column(String(50), default='restock')  # 'restock' or 'price_drop'
    target_price = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_stock_alerts_product_id', 'product_id'),
        Index('ix_stock_alerts_user_id', 'user_id'),
    )


class GiftVoucher(Base):
    __tablename__ = 'gift_vouchers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    amount = Column(Integer, nullable=False)
    creator_user_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    is_claimed = Column(Boolean, default=False)
    claimed_by_user_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    claimed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_gift_vouchers_code', 'code'),
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_order_number():
    return f"OXEL-{uuid.uuid4().hex[:6].upper()}"


def generate_delivery_code() -> str:
    """Generate a cryptographically random 6-digit delivery confirmation code."""
    return str(secrets.randbelow(900000) + 100000)


def create_tables():
    Base.metadata.create_all(engine)
    # Ensure newly added columns exist in SQLite database tables
    with engine.connect() as conn:
        from sqlalchemy import text
        migrations = [
            "ALTER TABLE orders ADD COLUMN phone VARCHAR(50);",
            "ALTER TABLE orders ADD COLUMN delivery_code VARCHAR(20);",
            "ALTER TABLE product_variants ADD COLUMN price_modifier INTEGER DEFAULT 0;",
            "ALTER TABLE product_variants ADD COLUMN is_active BOOLEAN DEFAULT 1;",
            "ALTER TABLE product_variants ADD COLUMN size_name VARCHAR(100);",
            "ALTER TABLE product_variants ADD COLUMN image_url VARCHAR(500);",
            "ALTER TABLE promo_codes ADD COLUMN start_date DATETIME;",
            "ALTER TABLE promo_codes ADD COLUMN expiration_date DATETIME;",
            "ALTER TABLE promo_codes ADD COLUMN max_uses INTEGER;",
            "ALTER TABLE promo_codes ADD COLUMN current_uses INTEGER DEFAULT 0;",
            "ALTER TABLE promo_codes ADD COLUMN per_user_limit INTEGER DEFAULT 1;",
            "ALTER TABLE promo_codes ADD COLUMN min_order_value INTEGER DEFAULT 0;",
            "ALTER TABLE promo_codes ADD COLUMN allowed_product_ids TEXT;",
            "ALTER TABLE promo_codes ADD COLUMN min_loyalty_tier VARCHAR(50);"
        ]
        for query in migrations:
            try:
                conn.execute(text(query))
                conn.commit()
            except Exception:
                pass


def seed_products():
    """Seed products, variant inventory stock, and promo codes."""
    import json
    import os
    db = SessionLocal()
    try:
        data_path = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
        with open(data_path, 'r') as f:
            products_data = json.load(f)

        default_stock_map = {
            "Natural Oak": 8,
            "Dark Walnut": 3,   # Low stock badge trigger!
            "Midnight Ash": 2   # Low stock badge trigger!
        }

        for p in products_data:
            existing = db.query(Product).filter(Product.slug == p['slug']).first()
            if existing:
                if p.get('image_url'):
                    existing.image_url = p['image_url']
                prod_obj = existing
            else:
                prod_obj = Product(
                    name=p['name'],
                    slug=p['slug'],
                    price=p['price'],
                    description=p['description'],
                    category=p['category'],
                    image_url=p.get('image_url'),
                    in_stock=p.get('in_stock', True),
                    avg_rating=p.get('avg_rating', 5.0),
                    review_count=p.get('review_count', 1)
                )
                db.add(prod_obj)
                db.flush()

            # Seed variant inventory stock per wood finish
            colors = p.get('colors', ["Natural Oak", "Dark Walnut", "Midnight Ash"])
            for finish_name in colors:
                var_exist = db.query(ProductVariant).filter(
                    ProductVariant.product_id == prod_obj.id,
                    ProductVariant.finish_name == finish_name
                ).first()
                if not var_exist:
                    init_qty = default_stock_map.get(finish_name, 5)
                    variant = ProductVariant(
                        product_id=prod_obj.id,
                        finish_name=finish_name,
                        stock_quantity=init_qty
                    )
                    db.add(variant)

        # Seed promo codes
        promos = [
            {"code": "OXEL10", "discount_percent": 10, "discount_amount": 0},
            {"code": "CREATOR15", "discount_percent": 15, "discount_amount": 0},
            {"code": "WELCOME500", "discount_percent": 0, "discount_amount": 500}
        ]
        for pr in promos:
            if not db.query(PromoCode).filter(PromoCode.code == pr['code']).first():
                db.add(PromoCode(**pr))

        db.commit()
        print("Database inventory stock, variant records, and promo codes synced.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    print("Initializing database tables and migrations...")
    create_tables()
    print("Seeding products, variants, and promo codes...")
    seed_products()
    print("Database setup complete!")

