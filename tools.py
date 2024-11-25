# tools.py
import asyncio
from datetime import datetime, timezone


def create_async_callback(async_func, *args, **kwargs):
    def wrapper():
        asyncio.create_task(async_func(*args, **kwargs))
    return wrapper


def days_difference_from_now(timestamp):
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    difference = now - date
    rounded_days = round(difference.total_seconds() / (24 * 3600))
    return rounded_days
