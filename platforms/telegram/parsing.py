import logging
import re
from datetime import datetime

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

from core.config import get_settings


settings = get_settings()
TIME_RANGE_PATTERN = re.compile(r"^(?P<start>\d{1,2}:\d{2})-(?P<end>\d{1,2}:\d{2})$")


def parse_game_datetime(value: str) -> datetime:
    try:
        date_time = parse(value)
        date_time = date_time.replace(tzinfo=settings.timezone)
        if date_time < datetime.now(tz=settings.timezone):
            date_time = date_time + relativedelta(months=1)
        return date_time
    except Exception as exc:
        logging.warning("Error while parsing date - %s", exc)
        raise ValueError("invalid date format") from exc


def parse_time_range(value: str) -> tuple[tuple[int, int], tuple[int, int]]:
    match = TIME_RANGE_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError("invalid time range format")

    try:
        start_hour, start_minute = (int(item) for item in match.group("start").split(":"))
        end_hour, end_minute = (int(item) for item in match.group("end").split(":"))
    except Exception as exc:
        raise ValueError("invalid time range format") from exc

    for hour, minute in ((start_hour, start_minute), (end_hour, end_minute)):
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("invalid time range value")

    return (start_hour, start_minute), (end_hour, end_minute)


def apply_time_range(date_time: datetime, value: str) -> tuple[datetime, int]:
    (start_hour, start_minute), (end_hour, end_minute) = parse_time_range(value)
    starts_at = date_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    ends_at = date_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

    duration_minutes = int((ends_at - starts_at).total_seconds() // 60)
    if duration_minutes <= 0:
        duration_minutes = settings.default_game_duration_minutes

    return starts_at, duration_minutes
