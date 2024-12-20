# gui.py
from PyQt5.QtWidgets import QApplication, QTabWidget, QVBoxLayout, QWidget, QStyleFactory, QMessageBox
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtCore import Qt
from config_tab import ConfigTab
from trade_tab import TradeTab
from trade_route_tab import TradeRouteTab
from best_trade_route import BestTradeRouteTab
from config_manager import ConfigManager
from translation_manager import TranslationManager
from api import API
import asyncio
from tools import translate


class UexcorpTrader(QWidget):
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __init__(self, app, loop, show_qmessagebox=True):
        super().__init__()
        self.app = app
        self.loop = loop
        self.config_manager = None
        self.translation_manager = None
        self.api = None
        self.show_qmessagebox = show_qmessagebox

    async def initialize(self):
        async with self._lock:
            if self.config_manager is None or self.translation_manager is None or self.api is None:
                self.config_manager = await ConfigManager.get_instance()
                self.translation_manager = await TranslationManager.get_instance()
                self.api = await API.get_instance(self.config_manager)
                await self.init_ui()
                await self.apply_appearance_mode(self.config_manager.get_appearance_mode())
                self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    async def init_ui(self):
        self.setWindowTitle(await translate("window_title"))
        self.setWindowIcon(QIcon("resources/UEXTrader_icon_resized.png"))

        if hasattr(self, "tabs") and hasattr(self, "main_layout"):
            self.main_layout.removeWidget(self.tabs)
        self.tabs = QTabWidget()
        self.configTab = ConfigTab(self)
        await self.configTab.initialize()
        self.tradeTab = TradeTab(self)
        await self.tradeTab.initialize()
        self.tradeRouteTab = TradeRouteTab(self)
        await self.tradeRouteTab.initialize()
        self.bestTradeRouteTab = BestTradeRouteTab(self)
        await self.bestTradeRouteTab.initialize()
        self.tabs.addTab(self.configTab, await translate("config_tab"))
        self.tabs.addTab(self.tradeTab, await translate("trade_tab"))
        self.tabs.addTab(self.tradeRouteTab, await translate("trade_route_tab"))
        self.tabs.addTab(self.bestTradeRouteTab, await translate("best_trade_route_tab"))

        if not hasattr(self, "main_layout"):
            self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.tabs)
        if not self.layout():
            self.setLayout(self.main_layout)

        # Restore window size
        width, height = self.config_manager.get_window_size()
        self.resize(width, height)

    async def cleanup(self):
        # Cleanup resources
        await self.api.cleanup()
        # Other cleanup...

    async def apply_appearance_mode(self, appearance_mode=None):
        if not appearance_mode:
            await self.ensure_initialized()
            appearance_mode = self.config_manager.get_appearance_mode()
        if appearance_mode == "Dark":
            self.app.setStyle(QStyleFactory.create("Fusion"))
            dark_palette = self.create_dark_palette()
            self.app.setPalette(dark_palette)
        else:
            self.app.setStyle(QStyleFactory.create("Fusion"))
            self.app.setPalette(QApplication.style().standardPalette())

    def create_dark_palette(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        return dark_palette

    def closeEvent(self, event):
        # Save window size
        self.config_manager.set_window_size(self.width(), self.height())
        super().closeEvent(event)
        self.loop.stop()
        self.loop.close()

    async def set_gui_enabled(self, enabled):
        await self.ensure_initialized()
        self.configTab.set_gui_enabled(enabled)
        self.tradeTab.set_gui_enabled(enabled)
        self.tradeRouteTab.set_gui_enabled(enabled)
        self.bestTradeRouteTab.set_gui_enabled(enabled)

    def show_messagebox(self, title, text, criticity=QMessageBox.Icon.Information):
        if self.show_qmessagebox:
            match criticity:
                case QMessageBox.Icon.Critical:
                    QMessageBox.critical(self, title, text)
                    return
                case QMessageBox.Icon.Warning:
                    QMessageBox.warning(self, title, text)
                    return
                case QMessageBox.Icon.Question:
                    QMessageBox.question(self, title, text)
                    return
                case _:
                    QMessageBox.information(self, title, text)
                    return
