import pytest
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtGui import QColor


@pytest.mark.asyncio
async def test_uexcorp_trader_init(trader):
    assert trader.windowTitle() == "UEX-Trader"
    assert not trader.windowIcon().isNull()
    assert trader.config_manager is not None
    assert trader.layout().count() > 0


@pytest.mark.asyncio
async def test_uexcorp_trader_apply_appearance_mode(trader, qapp):
    await trader.apply_appearance_mode("Dark")
    assert qapp.palette().color(trader.create_dark_palette().Window) == QColor(53, 53, 53)
    await trader.apply_appearance_mode("Light")
    assert qapp.palette().color(trader.create_dark_palette().Window) != QColor(53, 53, 53)


@pytest.mark.asyncio
async def test_tabs_exist(trader):
    """Test that all tabs are present."""
    tabs = trader.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 4
    assert tabs.tabText(0) == "Configuration"
    assert tabs.tabText(1) == "Trade Commodity"
    assert tabs.tabText(2) == "Find Trade Route"
    assert tabs.tabText(3) == "Best Trade Routes"
    assert tabs.tabText(4) == "Submit Terminal"
