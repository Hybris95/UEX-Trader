# tools.py
import asyncio
from datetime import datetime, timezone
from config_manager import ConfigManager
from translation_manager import TranslationManager


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


async def translate(key):
    config_manager = await ConfigManager.get_instance()
    translation_manager = await TranslationManager.get_instance()
    return translation_manager.get_translation(key, config_manager.get_lang())
