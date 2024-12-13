# conftest.py
import asyncio
from PyQt5.QtWidgets import QApplication
import pytest_asyncio
from gui import UexcorpTrader
from config_manager import ConfigManager


@pytest_asyncio.fixture(scope="session")
async def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


@pytest_asyncio.fixture(scope="session")
async def config_manager():
    config_manager = await ConfigManager.get_instance()
    await config_manager.initialize()  # Ensure this is asynchronous
    yield config_manager


@pytest_asyncio.fixture
async def trader(qapp):
    trader = UexcorpTrader(qapp, asyncio.get_event_loop())
    await trader.initialize()
    yield trader
    await trader.cleanup()
