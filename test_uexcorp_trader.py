# test_uexcorp_trader.py
import pytest
import asyncio
from PyQt5.QtWidgets import QApplication, QTabWidget
from PyQt5.QtGui import QColor
from qasync import QEventLoop
from gui import UexcorpTrader


@pytest.fixture
def app(qtbot):
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    yield app, loop
    loop.close()
    app.quit()


def test_uexcorp_trader_init(app, qtbot):
    app, loop = app
    trader = UexcorpTrader(app, loop)
    qtbot.addWidget(trader)
    assert trader.windowTitle() == "UEXcorp Trader"
    assert not trader.windowIcon().isNull()
    assert trader.config_manager is not None
    assert trader.layout().count() > 0


def test_uexcorp_trader_apply_appearance_mode(app, qtbot):
    app, loop = app
    trader = UexcorpTrader(app, loop)
    qtbot.addWidget(trader)
    trader.apply_appearance_mode("Dark")
    assert app.palette().color(trader.create_dark_palette().Window) == QColor(53, 53, 53)
    trader.apply_appearance_mode("Light")
    assert app.palette().color(trader.create_dark_palette().Window) != QColor(53, 53, 53)


def test_tabs_exist(app, qtbot):
    app, loop = app
    trader = UexcorpTrader(app, loop)
    qtbot.addWidget(trader)
    """Test that all tabs are present."""
    tabs = trader.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 4
    assert tabs.tabText(0) == "Configuration"
    assert tabs.tabText(1) == "Trade Commodity"
    assert tabs.tabText(2) == "Find Trade Route"
    assert tabs.tabText(3) == "Best Trade Routes"
