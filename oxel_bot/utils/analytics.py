"""Customer Personal Analytics & Eco CO2 Footprint Module."""
from database import SessionLocal, User, Order, Product


def get_customer_analytics(user_id: int) -> dict:
    db = SessionLocal()
    try:
        from utils.vip import sync_user_loyalty_and_vip
        vip_data = sync_user_loyalty_and_vip(db, user_id)

        user = db.query(User).filter(User.user_id == user_id).first()
        orders = db.query(Order).filter(Order.user_id == user_id).all()

        total_orders = len(orders)
        completed_orders = [o for o in orders if o.status in ['paid', 'confirmed', 'shipped', 'delivered']]
        total_spend = sum(o.total_price for o in completed_orders)

        # Estimate CO2 savings: ~1.8 kg CO2 saved per solid hardwood product vs plastic
        items_count = sum(o.quantity for o in completed_orders)
        co2_saved_kg = round(items_count * 1.8, 1)

        points = user.loyalty_points if user else 0

        return {
            "total_orders": total_orders,
            "completed_orders": len(completed_orders),
            "total_spend": total_spend,
            "items_bought": items_count,
            "co2_saved_kg": co2_saved_kg,
            "loyalty_points": points
        }
    finally:
        db.close()
