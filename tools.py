# tools.py
import asyncio
from datetime import datetime, timezone
from config_manager import ConfigManager
from translation_manager import TranslationManager
from metrics import Metrics
from PyQt5.QtWidgets import QProgressBar


@Metrics.track_sync_fnc_exec
def create_async_callback(async_func, *args, **kwargs):
    def wrapper():
        asyncio.create_task(async_func(*args, **kwargs))
    return wrapper


@Metrics.track_sync_fnc_exec
def days_difference_from_now(timestamp=0):
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    difference = now - date
    rounded_days = round(difference.total_seconds() / (24 * 3600))
    return rounded_days


@Metrics.track_async_fnc_exec
async def translate(key):
    config_manager = await ConfigManager.get_instance()
    translation_manager = await TranslationManager.get_instance()
    return translation_manager.get_translation(key, config_manager.get_lang())


@Metrics.track_sync_fnc_exec
def progress_qprogressbar(progress_bar: QProgressBar, value: int, format=None):
    progress_bar.setValue(value)
    if format:
        progress_bar.setFormat(format)
