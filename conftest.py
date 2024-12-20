# conftest.py
import asyncio
from PyQt5.QtWidgets import QApplication
import pytest_asyncio
from gui import UexcorpTrader


@pytest_asyncio.fixture(scope="session")
async def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


@pytest_asyncio.fixture()
async def config_manager(trader):
    yield trader.config_manager


@pytest_asyncio.fixture
async def trader(qapp):
    trader = UexcorpTrader(qapp, asyncio.get_event_loop(), show_qmessagebox=False)
    await trader.initialize()
    yield trader
