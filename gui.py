# gui.py
from PyQt5.QtWidgets import QApplication, QTabWidget, QVBoxLayout, QWidget, QStyleFactory, QMessageBox
from PyQt5.QtWidgets import QSplashScreen, QProgressBar
from PyQt5.QtGui import QIcon, QPalette, QColor, QPixmap
from PyQt5.QtCore import Qt, QTimer
from config_tab import ConfigTab
from trade_tab import TradeTab
from trade_route_tab import TradeRouteTab
from best_trade_route import BestTradeRouteTab
from submit_tab import SubmitTab
from config_manager import ConfigManager
from translation_manager import TranslationManager
from api import API
import asyncio
from tools import translate
from global_variables import trade_tab_activated, trade_route_tab_activated
from global_variables import best_trade_route_tab_activated, submit_tab_activated, metrics_tab_activated
from global_variables import load_systems_activated, load_planets_activated, load_terminals_activated
from global_variables import load_commodities_prices_activated, load_commodities_routes_activated
from global_variables import remove_obsolete_keys_activated
from metrics_widget import MetricsTab
from metrics import Metrics


class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__(QPixmap("_internal/resources/UEXTrader_splashscreen.png"))
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(20, self.height() - 50, self.width() - 40, 30)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.showMessage(message, Qt.AlignBottom | Qt.AlignCenter, Qt.white)


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

    @Metrics.track_sync_fnc_exec
    def _update_splash(self, value, message):
        def update():
            if self.splash:
                self.splash.update_progress(value, message)
                QApplication.processEvents()
        self.loop.call_soon_threadsafe(update)

    @Metrics.track_async_fnc_exec
    async def initialize(self):
        async with self._lock:
            if self.config_manager is None or self.translation_manager is None or self.api is None:
                self.splash = SplashScreen()
                self.splash.show()

                async def init_tasks():
                    self._update_splash(0, "Initializing Config Manager...")
                    self.config_manager = await ConfigManager.get_instance()
                    self._update_splash(1, "Initializing Translation Manager...")
                    self.translation_manager = await TranslationManager.get_instance()
                    self._update_splash(2, "Initializing API...")
                    self.api = await API.get_instance(self.config_manager)
                    await self._load_cache()  # Load Cache and detail
                    self._update_splash(98, "Initializing UI...")
                    await self.init_ui()
                    self._update_splash(99, "Applying Appearance Mode...")
                    await self.apply_appearance_mode(self.config_manager.get_appearance_mode())
                    self._update_splash(100, "Initialization Complete!")
                    QTimer.singleShot(1000, self.splash.close)  # Close splash after 1 second

                await asyncio.gather(init_tasks())
                self._initialized.set()

    @Metrics.track_async_fnc_exec
    async def _load_cache(self):
        self._splash_remove_obsolete_keys()
        await self._splash_load_systems()
        await self._splash_load_planets()
        await self._splash_load_terminals()
        await self._splash_load_commodities_prices()
        await self._splash_load_distances()

    @Metrics.track_sync_fnc_exec
    def _splash_remove_obsolete_keys(self):
        if remove_obsolete_keys_activated:
            self._update_splash(3, "Removing obsolete cache keys")
            self.api.cache.clean_obsolete()

    @Metrics.track_async_fnc_exec
    async def _splash_load_systems(self):
        if load_systems_activated:
            self._update_splash(10, "Initializing API Cache - Systems...")
            if not self.api.cache.endpoint_exists_in_cache("/star_systems"):
                await self.api.fetch_all_systems()

    @Metrics.track_async_fnc_exec
    async def _splash_load_planets(self):
        if load_planets_activated:
            self._update_splash(11, "Initializing API Cache - Planets...")
            if not self.api.cache.endpoint_exists_in_cache("/planets"):
                await self.api.fetch_planets()

    @Metrics.track_async_fnc_exec
    async def _splash_load_terminals(self):
        if load_terminals_activated:
            self._update_splash(13, "Initializing API Cache - Terminals...")
            if not self.api.cache.endpoint_exists_in_cache("/terminals"):
                await self.api.fetch_all_terminals()

    @Metrics.track_async_fnc_exec
    async def _splash_load_commodities_prices(self):
        if load_commodities_prices_activated:
            self._update_splash(15, "Initializing API Cache - Commodities...")
            if not self.api.cache.endpoint_exists_in_cache("/commodities_prices"):
                await self.api.fetch_all_commodities_prices()

    @Metrics.track_async_fnc_exec
    async def _splash_load_distances(self):
        if load_commodities_routes_activated:
            self._update_splash(55, "Initializing API Cache - Distances (Once per week)...")
            if not self.api.cache.endpoint_exists_in_cache("/commodities_routes"):
                await self.api.fetch_all_routes()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    @Metrics.track_async_fnc_exec
    async def init_ui(self):
        self.setWindowTitle(await translate("window_title"))
        self.setWindowIcon(QIcon("_internal/resources/UEXTrader_icon_resized.png"))

        if hasattr(self, "tabs") and hasattr(self, "main_layout"):
            self.main_layout.removeWidget(self.tabs)
        self.tabs = QTabWidget()
        self.configTab = ConfigTab(self)
        await self.configTab.initialize()
        self.tabs.addTab(self.configTab, await translate("config_tab"))
        if trade_tab_activated:
            self.tradeTab = TradeTab(self)
            await self.tradeTab.initialize()
            self.tabs.addTab(self.tradeTab, await translate("trade_tab"))
        if trade_route_tab_activated:
            self.tradeRouteTab = TradeRouteTab(self)
            await self.tradeRouteTab.initialize()
            self.tabs.addTab(self.tradeRouteTab, await translate("trade_route_tab"))
        if best_trade_route_tab_activated:
            self.bestTradeRouteTab = BestTradeRouteTab(self)
            await self.bestTradeRouteTab.initialize()
            self.tabs.addTab(self.bestTradeRouteTab, await translate("best_trade_route_tab"))
        if submit_tab_activated:
            self.submitTab = SubmitTab(self)
            await self.submitTab.initialize()
            self.tabs.addTab(self.submitTab, await translate("submit_tab"))
        if metrics_tab_activated:
            self.metricsWidget = MetricsTab(self)
            await self.metricsWidget.initialize()
            self.tabs.addTab(self.metricsWidget, "Metrics")

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

    @Metrics.track_async_fnc_exec
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

    @Metrics.track_sync_fnc_exec
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

    @Metrics.track_sync_fnc_exec
    def closeEvent(self, event):
        # Save window size
        self.config_manager.set_window_size(self.width(), self.height())
        super().closeEvent(event)
        self.loop.stop()
        self.loop.close()

    @Metrics.track_async_fnc_exec
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
