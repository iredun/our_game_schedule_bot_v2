import math
from datetime import datetime, timedelta
from core.config import get_settings


settings = get_settings()


def format_duration_minutes(duration_minutes: int) -> str:
    hours, minutes = divmod(duration_minutes, 60)
    if hours and minutes:
        return f"{hours}ч. {minutes}м."
    if hours:
        return f"{hours}ч."
    return f"{minutes}м."


def format_game_datetime_range(starts_at: datetime, duration_minutes: int) -> str:
    if starts_at.hour == 0 and starts_at.minute == 0:
        return starts_at.astimezone(settings.timezone).strftime("%d.%m.%Y")

    ends_at = starts_at + timedelta(minutes=duration_minutes)
    return f"{starts_at.astimezone(settings.timezone).strftime('%d.%m.%Y %H:%M')}-{ends_at.astimezone(settings.timezone).strftime('%H:%M')}"


def calculate_total_price(price_per_hour: int, duration_minutes: int) -> int:
    return math.ceil(price_per_hour * duration_minutes / 60)
