import math

# Megenagna, Addis Ababa coordinates
MEGENAGNA_LAT = 9.0203
MEGENAGNA_LON = 38.8023


def calculate_distance_km(lat1: float, lon1: float, lat2: float = MEGENAGNA_LAT, lon2: float = MEGENAGNA_LON) -> float:
    """Calculate distance in kilometers between two GPS coordinates using Haversine formula."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_delivery_fee(lat: float = None, lon: float = None) -> tuple[int, float]:
    """
    Calculate delivery fee based on radius from Megenagna, Addis Ababa.
    - Default fee for manual address without GPS: 200 ETB
    - With GPS coordinates: 30 ETB per kilometer, rounded up to the next whole kilometer.
    - Returns tuple: (delivery_fee_etb, distance_km)
    """
    if lat is None or lon is None:
        return 200, 0.0  # Default fee for manual address without GPS

    dist_km = calculate_distance_km(lat, lon)
    if dist_km <= 0:
        return 200, 0.0

    fee = max(200, math.ceil(dist_km) * 30)
    return fee, dist_km
