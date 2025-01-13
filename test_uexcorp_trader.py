import pytest
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtGui import QColor
from global_variables import trade_tab_activated, trade_route_tab_activated
from global_variables import best_trade_route_tab_activated, submit_tab_activated


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
    count_expected = (int(trade_tab_activated) + int(trade_route_tab_activated)
                      + int(best_trade_route_tab_activated) + int(submit_tab_activated))
    assert tabs is not None
    assert tabs.count() == count_expected
    current_count = 0
    assert tabs.tabText(current_count) == "Configuration"
    if trade_tab_activated:
        current_count += 1
        assert tabs.tabText(current_count) == "Trade Commodity"
    if trade_route_tab_activated:
        current_count += 1
        assert tabs.tabText(current_count) == "Find Trade Route"
    if best_trade_route_tab_activated:
        current_count += 1
        assert tabs.tabText(current_count) == "Best Trade Routes"
    if submit_tab_activated:
        current_count += 1
        assert tabs.tabText(current_count) == "Submit Terminal"
