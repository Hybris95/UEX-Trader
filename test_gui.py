import pytest
import asyncio
from qasync import QEventLoop
from PyQt5.QtWidgets import QApplication, QTabWidget
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt
from gui import UexcorpTrader
import sys


@pytest.fixture
def app():
    """Fixture for creating the QApplication instance."""
    app = QApplication(sys.argv)
    yield app
    app.quit()


@pytest.fixture
def trader(app, qtbot):
    """Fixture for creating the UexcorpTrader instance."""
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    trader = UexcorpTrader(app, loop)
    qtbot.addWidget(trader)

    return trader


def test_initial_ui_state(trader):
    """Test the initial state of the UI."""
    assert trader.windowTitle() == "UEXcorp Trader"
    assert not trader.windowIcon().isNull()
    assert trader.layout().count() > 0


def test_tabs_exist(trader):
    """Test that all tabs are present."""
    tabs = trader.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 4
    assert tabs.tabText(0) == "Configuration"
    assert tabs.tabText(1) == "Trade Commodity"
    assert tabs.tabText(2) == "Find Trade Route"
    assert tabs.tabText(3) == "Best Trade Routes"


def test_dark_mode(trader):
    """Test the dark mode appearance."""
    trader.apply_appearance_mode("Dark")
    palette = trader.app.palette()
    assert palette.color(QPalette.Window) == QColor(53, 53, 53)
    assert palette.color(QPalette.WindowText) == Qt.white


def test_light_mode(trader):
    """Test the light mode appearance."""
    trader.apply_appearance_mode("Light")
    palette = trader.app.palette()
    assert palette.color(QPalette.Window) != QColor(53, 53, 53)
    assert palette.color(QPalette.WindowText) != Qt.white
