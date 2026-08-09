from datetime import datetime


def format_price(amount: int) -> str:
    """Format price with comma separators and ETB suffix."""
    return f"{amount:,} ETB"


def format_date(dt: datetime) -> str:
    """Format datetime for display."""
    return dt.strftime('%b %d, %Y · %I:%M %p')


def format_date_short(dt: datetime) -> str:
    """Format datetime in short form."""
    return dt.strftime('%b %d, %Y')


STATUS_EMOJI = {
    'pending': '⏳',
    'paid': '✅',
    'confirmed': '📦',
    'shipped': '🚚',
    'delivered': '🏠',
    'cancelled': '❌'
}

STATUS_LABELS = {
    'pending': 'Pending Verification',
    'paid': 'Payment Verified',
    'confirmed': 'Order Confirmed',
    'shipped': 'Shipped',
    'delivered': 'Delivered',
    'cancelled': 'Cancelled'
}


def get_status_display(status: str) -> str:
    """Get formatted status with emoji."""
    emoji = STATUS_EMOJI.get(status, '📌')
    label = STATUS_LABELS.get(status, status.upper())
    return f"{emoji} {label}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + '...'
