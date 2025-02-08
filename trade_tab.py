import logging
import aiohttp
import re
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QListWidget
from PyQt5.QtWidgets import QLineEdit, QPushButton, QMessageBox, QListWidgetItem, QTabWidget
from PyQt5.QtCore import Qt
import asyncio
from api import API
from config_manager import ConfigManager
from translation_manager import TranslationManager
from tools import translate
import traceback
from metrics import Metrics


class TradeTab(QWidget):
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.config_manager = None
        self.api = None
        self.translation_manager = None
        self._current_terminal_commodities = []
        self._unfiltered_terminals = []
        asyncio.ensure_future(self.load_systems())

    @Metrics.track_async_fnc_exec
    async def initialize(self):
        async with self._lock:
            if self.config_manager is None or self.translation_manager is None or self.api is None:
                self.config_manager = await ConfigManager.get_instance()
                self.api = await API.get_instance(self.config_manager)
                self.translation_manager = await TranslationManager.get_instance()
                await self.init_ui()
                self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    @Metrics.track_async_fnc_exec
    async def init_ui(self):
        main_layout = QVBoxLayout()
        system_label = QLabel(await translate("select_system") + ":")
        self.system_combo = QComboBox()
        self.system_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_planets()))
        main_layout.addWidget(system_label)
        main_layout.addWidget(self.system_combo)

        planet_label = QLabel(await translate("select_planet") + ":")
        self.planet_combo = QComboBox()
        self.planet_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_terminals()))
        main_layout.addWidget(planet_label)
        main_layout.addWidget(self.planet_combo)

        terminal_label = QLabel(await translate("select_terminal") + ":")
        self.terminal_filter_input = QLineEdit()
        self.terminal_filter_input.setPlaceholderText(await translate("filter_terminals"))
        self.terminal_filter_input.textChanged.connect(self.filter_terminals)
        self.terminal_combo = QComboBox()
        self.terminal_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_commodities()))
        main_layout.addWidget(terminal_label)
        main_layout.addWidget(self.terminal_filter_input)
        main_layout.addWidget(self.terminal_combo)

        commodity_buy_label = QLabel(await translate("commodities_to_buy") + ":")
        self.commodity_buy_list = QListWidget()
        self.commodity_buy_list.currentItemChanged.connect(self.update_buy_price)
        main_layout.addWidget(commodity_buy_label)
        main_layout.addWidget(self.commodity_buy_list)

        commodity_sell_label = QLabel(await translate("commodities_to_sell") + ":")
        self.commodity_sell_list = QListWidget()
        self.commodity_sell_list.currentItemChanged.connect(self.update_sell_price)
        main_layout.addWidget(commodity_sell_label)
        main_layout.addWidget(self.commodity_sell_list)

        quantity_label = QLabel(await translate("quantity") + " (" + await translate("scu") + "):")
        self.quantity_input = QLineEdit()
        main_layout.addWidget(quantity_label)
        main_layout.addWidget(self.quantity_input)

        buy_price_label = QLabel(await translate("trade_columns_buy_price") + ":")
        self.buy_price_input = QLineEdit()
        main_layout.addWidget(buy_price_label)
        main_layout.addWidget(self.buy_price_input)

        sell_price_label = QLabel(await translate("trade_columns_sell_price") + ":")
        self.sell_price_input = QLineEdit()
        main_layout.addWidget(sell_price_label)
        main_layout.addWidget(self.sell_price_input)

        self.buy_button = QPushButton(await translate("declare_purchase"))
        self.buy_button.setEnabled(False)
        self.buy_button.clicked.connect(lambda: asyncio.ensure_future(self.buy_commodity()))
        main_layout.addWidget(self.buy_button)

        self.sell_button = QPushButton(await translate("declare_sale"))
        self.sell_button.setEnabled(False)
        self.sell_button.clicked.connect(lambda: asyncio.ensure_future(self.sell_commodity()))
        main_layout.addWidget(self.sell_button)

        self.setLayout(main_layout)

    @Metrics.track_async_fnc_exec
    async def load_systems(self):
        try:
            await self.ensure_initialized()
            self.system_combo.clear()
            for system in (await self.api.fetch_all_systems()):
                self.system_combo.blockSignals(True)
                self.system_combo.addItem(system["name"], system["id"])
                if system.get("is_default") == 1:
                    self.system_combo.blockSignals(False)
                    self.system_combo.setCurrentIndex(self.system_combo.count() - 1)
            logging.info("Systems loaded successfully.")
        except Exception as e:
            logging.error("Failed to load systems: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            self.main_widget.show_messagebox(await translate("error_error"),
                                             await translate("error_failed_to_load_systems") + ": " + str(e),
                                             QMessageBox.Icon.Critical)
        finally:
            self.system_combo.blockSignals(False)

    @Metrics.track_async_fnc_exec
    async def update_planets(self):
        await self.ensure_initialized()
        self.planet_combo.clear()
        system_id = self.system_combo.currentData()
        if not system_id:
            return
        try:
            for planet in (await self.api.fetch_planets(system_id)):
                self.planet_combo.addItem(planet["name"], planet["id"])
            self.planet_combo.addItem(await translate("unknown_planet"), 0)
            logging.info("Planets loaded successfully for star_system ID : %s", system_id)
        except Exception as e:
            logging.error("Failed to load planets: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            self.main_widget.show_messagebox(await translate("error_error"),
                                             await translate("error_failed_to_load_planets") + ": " + str(e),
                                             QMessageBox.Icon.Critical)

    @Metrics.track_async_fnc_exec
    async def update_terminals(self):
        await self.ensure_initialized()
        self.terminal_combo.clear()
        self.terminal_filter_input.clear()
        self._unfiltered_terminals = []
        planet_id = self.planet_combo.currentData()
        system = self.system_combo.currentData()
        try:
            if not planet_id:
                if system:
                    self._unfiltered_terminals = [terminal for terminal in (await self.api.fetch_terminals_by_system(system))
                                                  if terminal.get("id_planet") == 0]
                    logging.info("Terminals loaded successfully for system ID (Unknown planet): %s", system)
            else:
                self._unfiltered_terminals = await self.api.fetch_terminals_by_planet(planet_id)
                logging.info("Terminals loaded successfully for planet ID : %s", planet_id)
        except Exception as e:
            logging.error("Failed to load terminals: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            self.main_widget.show_messagebox(await translate("error_error"),
                                             await translate("error_failed_to_load_terminals") + ": " + str(e),
                                             QMessageBox.Icon.Critical)
        finally:
            self.filter_terminals()
        return self._unfiltered_terminals

    @Metrics.track_sync_fnc_exec
    def filter_terminals(self, terminal_id=None):
        filter_text = self.terminal_filter_input.text().lower()
        self.terminal_combo.clear()
        for terminal in self._unfiltered_terminals:
            if filter_text in terminal["name"].lower():
                self.terminal_combo.addItem(terminal["name"], terminal["id"])
        if terminal_id:
            index = self.terminal_combo.findData(terminal_id)
            if index != -1:
                self.terminal_combo.setCurrentIndex(index)

    @Metrics.track_async_fnc_exec
    async def update_commodities(self):
        await self.ensure_initialized()
        self.commodity_buy_list.clear()
        self.commodity_sell_list.clear()
        self.buy_price_input.clear()
        self.sell_price_input.clear()
        self.buy_button.setEnabled(False)
        self.sell_button.setEnabled(False)
        terminal_id = self.terminal_combo.currentData()
        if not terminal_id:
            return
        try:
            self._current_terminal_commodities = await self.api.fetch_commodities_from_terminal(terminal_id)
            for commodity in self._current_terminal_commodities:
                item = QListWidgetItem(commodity["commodity_name"])
                item.setData(Qt.UserRole, commodity["id_commodity"])
                if commodity["price_buy"] > 0:
                    self.commodity_buy_list.addItem(item)
                if commodity["price_sell"] > 0:
                    self.commodity_sell_list.addItem(item)
            logging.info("Commodities loaded successfully for terminal ID : %s", terminal_id)
        except Exception as e:
            logging.error("Failed to load commodities: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            self.main_widget.show_messagebox(await translate("error_error"),
                                             await translate("error_failed_to_load_commodities") + ": " + str(e),
                                             QMessageBox.Icon.Critical)

    @Metrics.track_sync_fnc_exec
    def update_buy_price(self, current_item, previous_item):
        if current_item:
            commodity_id = current_item.data(Qt.UserRole)
            commodity = next((c for c in self._current_terminal_commodities
                              if c["id_commodity"] == commodity_id), None)
            if commodity:
                self.buy_price_input.setText(str(commodity["price_buy"]))
            self.buy_button.setEnabled(True)
        else:
            self.buy_price_input.clear()
            self.buy_button.setEnabled(False)

    @Metrics.track_sync_fnc_exec
    def update_sell_price(self, current_item, previous_item):
        if current_item:
            commodity_id = current_item.data(Qt.UserRole)
            commodity = next((c for c in self._current_terminal_commodities
                              if c["id_commodity"] == commodity_id), None)
            if commodity:
                self.sell_price_input.setText(str(commodity["price_sell"]))
            self.sell_button.setEnabled(True)
        else:
            self.sell_price_input.clear()
            self.sell_button.setEnabled(False)

    @Metrics.track_async_fnc_exec
    async def buy_commodity(self):
        await self.perform_trade(self.commodity_buy_list, is_buy=True)

    @Metrics.track_async_fnc_exec
    async def sell_commodity(self):
        await self.perform_trade(self.commodity_sell_list, is_buy=False)

    @Metrics.track_async_fnc_exec
    async def perform_trade(self, commodity_list, is_buy):
        await self.ensure_initialized()
        selected_item = commodity_list.currentItem()
        if not selected_item:
            self.main_widget.show_messagebox(await translate("error_error"), await translate("error_input_select_comm"),
                                             QMessageBox.Icon.Warning)
            return

        operation = "buy" if is_buy else "sell"
        price_input = self.buy_price_input if is_buy else self.sell_price_input

        logger = logging.getLogger(__name__)
        try:
            planet_id = self.planet_combo.currentData()
            terminal_id = self.terminal_combo.currentData()
            id_commodity = selected_item.data(Qt.UserRole)
            quantity = self.quantity_input.text()
            price = price_input.text()

            logger.debug("Attempting trade - Operation: %s, Terminal ID: %s, Commodity ID: %s, Quantity: %s, Price: %s",
                         operation, terminal_id, id_commodity, quantity, price)

            await self.validate_trade_inputs(terminal_id, id_commodity, quantity, price)
            await self.validate_terminal_and_commodity(planet_id, terminal_id, id_commodity)

            data = {
                "id_terminal": terminal_id,
                "id_commodity": id_commodity,
                "operation": operation,
                "scu": int(quantity),
                "price": float(price),
            }

            result = await self.api.perform_trade(data)

            await self.handle_trade_result(result, logger)
        except aiohttp.ClientResponseError as e:
            if e.status == 403:
                logger.warning("API Key given is absent or invalid")
                self.main_widget.show_messagebox(await translate("error_input_api_invalid"),
                                                 await translate("error_input_api_invalid_details"),
                                                 QMessageBox.Icon.Warning)
            else:
                logger.exception("An unexpected error occurred: %s", e)
                self.main_widget.show_messagebox(await translate("error_error"),
                                                 await translate("error_generic") + ": " + str(e),
                                                 QMessageBox.Icon.Critical)
        except ValueError as e:
            logger.warning("Input Error: %s", e)
            self.main_widget.show_messagebox(await translate("error_input_error"), str(e),
                                             QMessageBox.Icon.Warning)
        except Exception as e:
            logger.exception("An unexpected error occurred: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            self.main_widget.show_messagebox(await translate("error_error"),
                                             await translate("error_generic") + ": " + str(e),
                                             QMessageBox.Icon.Critical)

    @Metrics.track_async_fnc_exec
    async def validate_trade_inputs(self, terminal_id, id_commodity, quantity, price):
        await self.ensure_initialized()
        if not all([terminal_id, id_commodity, quantity, price]):
            raise ValueError(await translate("error_input_fill_all_fields"))
        if not re.match(r'^\d+$', quantity):
            raise ValueError(await translate("quantity") + " " + await translate("error_input_invalid_integer"))
        if not re.match(r'^\d+(\.\d+)?$', price):
            raise ValueError(await translate("price") + " " + await translate("error_input_invalid_number"))

    @Metrics.track_async_fnc_exec
    async def validate_terminal_and_commodity(self, planet_id, terminal_id, id_commodity):
        await self.ensure_initialized()
        if not any(terminal.get('id') == terminal_id for terminal in (await self.api.fetch_terminals_by_planet(planet_id))):
            raise ValueError(await translate("error_input_invalid_terminal"))
        if not any(commodity["id_commodity"] == id_commodity for commodity in self._current_terminal_commodities):
            raise ValueError(await translate("error_input_commodity_doesnt_exist"))

    @Metrics.track_async_fnc_exec
    async def handle_trade_result(self, result, logger):
        await self.ensure_initialized()
        if result and "data" in result and "id_user_trade" in result["data"]:
            trade_id = result["data"].get('id_user_trade')
            logger.info("Trade successful! Trade ID: %s", trade_id)
            self.main_widget.show_messagebox(await translate("success_success"),
                                             await translate("success_trade_successful") + "!\n"
                                             + await translate("trade_id") + f": {trade_id}",
                                             QMessageBox.Icon.Information)
        else:
            error_message = result.get('message', 'Unknown error')
            logger.error("Trade failed: %s", error_message)
            self.main_widget.show_messagebox(await translate("error_error"),
                                             await translate("error_trade_failed") + f": {error_message}",
                                             QMessageBox.Icon.Critical)

    @Metrics.track_async_fnc_exec
    async def select_trade_route(self, trade_route, is_buy):
        logger = logging.getLogger(__name__)
        action = "buy" if is_buy else "sell"
        logger.info("Selecting trade route to %s commodity.", action)
        logger.debug(trade_route)

        tab_manager = self.main_widget.findChild(QTabWidget)
        tab_manager.setCurrentIndex(1)

        self.system_combo.blockSignals(True)
        self.planet_combo.blockSignals(True)
        self.terminal_combo.blockSignals(True)

        system_id = trade_route["departure_system_id"] if is_buy else trade_route["arrival_system_id"]
        self.system_combo.setCurrentIndex(self.system_combo.findData(system_id))
        logger.info("Selected system ID: %s", system_id)
        await self.update_planets()

        planet_id = trade_route["departure_planet_id"] if is_buy else trade_route["arrival_planet_id"]
        self.planet_combo.setCurrentIndex(self.planet_combo.findData(planet_id))
        logger.info("Selected planet ID: %s", planet_id)

        terminal_id = trade_route["departure_terminal_id"] if is_buy else trade_route["arrival_terminal_id"]
        await self.update_terminals()
        if terminal_id in [terminal["id"] for terminal in self._unfiltered_terminals]:
            self.filter_terminals(terminal_id)
            logger.info("Selected terminal ID: %s", terminal_id)
        else:
            logger.warning("Terminal ID %s not found in the list of terminals", terminal_id)

        await self.update_commodities()

        commodity_list = self.commodity_buy_list if is_buy else self.commodity_sell_list
        commodity_id = trade_route["commodity_id"]
        for i in range(commodity_list.count()):
            item = commodity_list.item(i)
            if item.data(Qt.UserRole) == commodity_id:
                commodity_list.setCurrentItem(item)
                logger.info("Selected commodity ID: %s", commodity_id)
                break

        self.quantity_input.setText(str(trade_route["max_buyable_scu"]))
        logger.info("Set quantity to: %s", trade_route['max_buyable_scu'])

        self.terminal_combo.blockSignals(False)
        self.planet_combo.blockSignals(False)
        self.system_combo.blockSignals(False)

    @Metrics.track_sync_fnc_exec
    def set_gui_enabled(self, enabled):
        for lineedit in self.findChildren(QLineEdit):
            lineedit.setEnabled(enabled)
        for combo in self.findChildren(QComboBox):
            combo.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)
        if enabled:
            self.update_buy_price(self.commodity_buy_list.currentItem(), None)
            self.update_sell_price(self.commodity_sell_list.currentItem(), None)
