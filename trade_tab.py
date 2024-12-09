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


class TradeTab(QWidget):
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.config_manager = None
        self.api = None
        self.translation_manager = None
        self.commodities = []
        self.terminals = []
        asyncio.ensure_future(self.load_systems())

    async def initialize(self):
        async with self._lock:
            if self.config_manager is None or self.translation_manager is None or self.api is None:
                # Initial the ConfigManager instance only once
                if ConfigManager._instance is None:
                    self.config_manager = ConfigManager()
                    await self.config_manager.initialize()
                else:
                    self.config_manager = ConfigManager._instance
                # Initialize the API instance only once
                if API._instance is None:
                    self.api = API(self.config_manager)
                    await self.api.initialize()
                else:
                    self.api = API._instance
                # Initialize the TranslationManager instance only once
                if TranslationManager._instance is None:
                    self.translation_manager = TranslationManager()
                    await self.translation_manager.initialize()
                else:
                    self.translation_manager = TranslationManager._instance
                await self.initUI()
                self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    async def initUI(self):
        main_layout = QVBoxLayout()
        system_label = QLabel(self.translation_manager.get_translation("select_system",
                                                                       self.config_manager.get_lang())+":")
        self.system_combo = QComboBox()
        self.system_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_planets()))
        main_layout.addWidget(system_label)
        main_layout.addWidget(self.system_combo)

        planet_label = QLabel(self.translation_manager.get_translation("select_planet",
                                                                       self.config_manager.get_lang())+":")
        self.planet_combo = QComboBox()
        self.planet_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_terminals()))
        main_layout.addWidget(planet_label)
        main_layout.addWidget(self.planet_combo)

        terminal_label = QLabel(self.translation_manager.get_translation("select_terminal",
                                                                         self.config_manager.get_lang())+":")
        self.terminal_filter_input = QLineEdit()
        self.terminal_filter_input.setPlaceholderText(self.translation_manager.get_translation("filter_terminals",
                                                                                               self.config_manager.get_lang()))
        self.terminal_filter_input.textChanged.connect(self.filter_terminals)
        self.terminal_combo = QComboBox()
        self.terminal_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_commodities()))
        main_layout.addWidget(terminal_label)
        main_layout.addWidget(self.terminal_filter_input)
        main_layout.addWidget(self.terminal_combo)

        commodity_buy_label = QLabel(self.translation_manager.get_translation("commodities_to_buy",
                                                                              self.config_manager.get_lang())+":")
        self.commodity_buy_list = QListWidget()
        self.commodity_buy_list.currentItemChanged.connect(self.update_buy_price)
        main_layout.addWidget(commodity_buy_label)
        main_layout.addWidget(self.commodity_buy_list)

        commodity_sell_label = QLabel(self.translation_manager.get_translation("commodities_to_sell",
                                                                               self.config_manager.get_lang())+":")
        self.commodity_sell_list = QListWidget()
        self.commodity_sell_list.currentItemChanged.connect(self.update_sell_price)
        main_layout.addWidget(commodity_sell_label)
        main_layout.addWidget(self.commodity_sell_list)

        quantity_label = QLabel(self.translation_manager.get_translation("quantity",
                                                                         self.config_manager.get_lang())
                                + " (" + self.translation_manager.get_translation("scu",
                                                                                  self.config_manager.get_lang()) + "):")
        self.quantity_input = QLineEdit()
        main_layout.addWidget(quantity_label)
        main_layout.addWidget(self.quantity_input)

        buy_price_label = QLabel(self.translation_manager.get_translation("trade_columns_buy_price",
                                                                          self.config_manager.get_lang())+":")
        self.buy_price_input = QLineEdit()
        main_layout.addWidget(buy_price_label)
        main_layout.addWidget(self.buy_price_input)

        sell_price_label = QLabel(self.translation_manager.get_translation("trade_columns_sell_price",
                                                                           self.config_manager.get_lang())+":")
        self.sell_price_input = QLineEdit()
        main_layout.addWidget(sell_price_label)
        main_layout.addWidget(self.sell_price_input)

        self.buy_button = QPushButton(self.translation_manager.get_translation("declare_purchase",
                                                                               self.config_manager.get_lang()))
        self.buy_button.setEnabled(False)
        self.buy_button.clicked.connect(lambda: asyncio.ensure_future(self.buy_commodity()))
        main_layout.addWidget(self.buy_button)

        self.sell_button = QPushButton(self.translation_manager.get_translation("declare_sale",
                                                                                self.config_manager.get_lang()))
        self.sell_button.setEnabled(False)
        self.sell_button.clicked.connect(lambda: asyncio.ensure_future(self.sell_commodity()))
        main_layout.addWidget(self.sell_button)

        self.setLayout(main_layout)

    async def load_systems(self):
        try:
            await self.ensure_initialized()
            self.system_combo.clear()
            systems = await self.api.fetch_data("/star_systems")
            for system in systems.get("data", []):
                if system.get("is_available") == 1:
                    self.system_combo.blockSignals(True)
                    self.system_combo.addItem(system["name"], system["id"])
                    if system.get("is_default") == 1:
                        self.system_combo.blockSignals(False)
                        self.system_combo.setCurrentIndex(self.system_combo.count() - 1)
            logging.info("Systems loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load systems: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_systems",
                                                                          self.config_manager.get_lang())
                                 + ": " + str(e))
        finally:
            self.system_combo.blockSignals(False)

    async def update_planets(self):
        await self.ensure_initialized()
        self.planet_combo.clear()
        system_id = self.system_combo.currentData()
        if not system_id:
            return
        try:
            planets = await self.api.fetch_data("/planets", params={'id_star_system': system_id})
            for planet in planets.get("data", []):
                self.planet_combo.addItem(planet["name"], planet["id"])
            self.planet_combo.addItem(self.translation_manager.get_translation("unknown_planet",
                                                                               self.config_manager.get_lang()), 0)
            logging.info(f"Planets loaded successfully for star_system ID : {system_id}")
        except Exception as e:
            logging.error(f"Failed to load planets: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_planets",
                                                                          self.config_manager.get_lang())
                                 + ": " + str(e))

    async def update_terminals(self):
        await self.ensure_initialized()
        self.terminal_combo.clear()
        self.terminal_filter_input.clear()
        self.terminals = []
        planet_id = self.planet_combo.currentData()
        system_id = self.system_combo.currentData()
        try:
            terminals = []
            if not planet_id:
                if system_id:
                    terminals = await self.api.fetch_data("/terminals", params={'id_star_system': system_id})
                    self.terminals = [terminal for terminal in terminals.get("data", [])
                                      if terminal.get("type") == "commodity" and terminal.get("is_available") == 1
                                      and terminal.get("id_planet") == 0]
                    logging.info(f"Terminals loaded successfully for system ID (Unknown planet): {system_id}")
            else:
                terminals = await self.api.fetch_data("/terminals", params={'id_planet': planet_id})
                self.terminals = [terminal for terminal in terminals.get("data", [])
                                  if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
                logging.info(f"Terminals loaded successfully for planet ID : {planet_id}")
        except Exception as e:
            logging.error(f"Failed to load terminals: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_terminals",
                                                                          self.config_manager.get_lang())
                                 + ": " + str(e))
        finally:
            self.filter_terminals()
            return self.terminals

    def filter_terminals(self, terminal_id=None):
        filter_text = self.terminal_filter_input.text().lower()
        self.terminal_combo.clear()
        for terminal in self.terminals:
            if filter_text in terminal["name"].lower():
                self.terminal_combo.addItem(terminal["name"], terminal["id"])
        if terminal_id:
            index = self.terminal_combo.findData(terminal_id)
            if index != -1:
                self.terminal_combo.setCurrentIndex(index)

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
            commodities = await self.api.fetch_data("/commodities_prices", params={'id_terminal': terminal_id})
            self.commodities = commodities.get("data", [])
            for commodity in self.commodities:
                item = QListWidgetItem(commodity["commodity_name"])
                item.setData(Qt.UserRole, commodity["id_commodity"])
                if commodity["price_buy"] > 0:
                    self.commodity_buy_list.addItem(item)
                if commodity["price_sell"] > 0:
                    self.commodity_sell_list.addItem(item)
            logging.info(f"Commodities loaded successfully for terminal ID : {terminal_id}")
        except Exception as e:
            logging.error(f"Failed to load commodities: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_commodities",
                                                                          self.config_manager.get_lang())
                                 + ": " + str(e))

    def update_buy_price(self, current, previous):
        if current:
            commodity_id = current.data(Qt.UserRole)
            commodity = next((c for c in self.commodities if c["id_commodity"] == commodity_id), None)
            if commodity:
                self.buy_price_input.setText(str(commodity["price_buy"]))
            self.buy_button.setEnabled(True)
        else:
            self.buy_price_input.clear()
            self.buy_button.setEnabled(False)

    def update_sell_price(self, current, previous):
        if current:
            commodity_id = current.data(Qt.UserRole)
            commodity = next((c for c in self.commodities if c["id_commodity"] == commodity_id), None)
            if commodity:
                self.sell_price_input.setText(str(commodity["price_sell"]))
            self.sell_button.setEnabled(True)
        else:
            self.sell_price_input.clear()
            self.sell_button.setEnabled(False)

    async def buy_commodity(self):
        await self.perform_trade(self.commodity_buy_list, is_buy=True)

    async def sell_commodity(self):
        await self.perform_trade(self.commodity_sell_list, is_buy=False)

    async def perform_trade(self, commodity_list, is_buy):
        await self.ensure_initialized()
        selected_item = commodity_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, self.translation_manager.get_translation("error_error",
                                                                               self.config_manager.get_lang()),
                                self.translation_manager.get_translation("error_input_select_comm",
                                                                         self.config_manager.get_lang()))
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

            logger.debug(f"Attempting trade - Operation: {operation}, Terminal ID: {terminal_id}, "
                         f"Commodity ID: {id_commodity}, Quantity: {quantity}, Price: {price}")

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
                QMessageBox.warning(self, self.translation_manager.get_translation("error_input_api_invalid",
                                                                                   self.config_manager.get_lang()),
                                    self.translation_manager.get_translation("error_input_api_invalid_details",
                                                                             self.config_manager.get_lang()))
            else:
                logger.exception(f"An unexpected error occurred: {e}")
                QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                    self.config_manager.get_lang()),
                                     self.translation_manager.get_translation("error_generic",
                                                                              self.config_manager.get_lang()) + ": " + str(e))
        except ValueError as e:
            logger.warning(f"Input Error: {e}")
            QMessageBox.warning(self, self.translation_manager.get_translation("error_input_error",
                                                                               self.config_manager.get_lang()), str(e))
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error", self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_generic",
                                                                          self.config_manager.get_lang())
                                 + ": " + str(e))

    async def validate_trade_inputs(self, terminal_id, id_commodity, quantity, price):
        await self.ensure_initialized()
        if not all([terminal_id, id_commodity, quantity, price]):
            raise ValueError(self.translation_manager.get_translation("error_input_fill_all_fields",
                                                                      self.config_manager.get_lang()))
        if not re.match(r'^\d+$', quantity):
            raise ValueError(self.translation_manager.get_translation("quantity",
                                                                      self.config_manager.get_lang())
                             + " "
                             + self.translation_manager.get_translation("error_input_invalid_integer",
                                                                        self.config_manager.get_lang()))
        if not re.match(r'^\d+(\.\d+)?$', price):
            raise ValueError(self.translation_manager.get_translation("price",
                                                                      self.config_manager.get_lang())
                             + " "
                             + self.translation_manager.get_translation("error_input_invalid_number",
                                                                        self.config_manager.get_lang()))

    async def validate_terminal_and_commodity(self, planet_id, terminal_id, id_commodity):
        await self.ensure_initialized()
        terminals = await self.api.fetch_data("/terminals", params={'id_planet': planet_id})
        if not any(terminal.get('id') == terminal_id for terminal in terminals.get("data", [])):
            raise ValueError(self.translation_manager.get_translation("error_input_invalid_terminal",
                                                                      self.config_manager.get_lang()))
        if not any(commodity["id_commodity"] == id_commodity for commodity in self.commodities):
            raise ValueError(self.translation_manager.get_translation("error_input_commodity_doesnt_exist",
                                                                      self.config_manager.get_lang()))

    async def handle_trade_result(self, result, logger):
        await self.ensure_initialized()
        if result and "data" in result and "id_user_trade" in result["data"]:
            trade_id = result["data"].get('id_user_trade')
            logger.info(f"Trade successful! Trade ID: {trade_id}")
            QMessageBox.information(self, self.translation_manager.get_translation("success_success",
                                                                                   self.config_manager.get_lang()),
                                    self.translation_manager.get_translation("success_trade_successful",
                                                                             self.config_manager.get_lang()) + "!\n"
                                    + self.translation_manager.get_translation("trade_id",
                                                                               self.config_manager.get_lang())
                                    + f": {trade_id}")
        else:
            error_message = result.get('message', 'Unknown error')
            logger.error(f"Trade failed: {error_message}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error", self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_trade_failed", self.config_manager.get_lang())
                                 + f": {error_message}")

    async def select_trade_route(self, trade_route, is_buy):
        logger = logging.getLogger(__name__)
        action = "buy" if is_buy else "sell"
        logger.info(f"Selecting trade route to {action} commodity.")
        logger.debug(trade_route)

        tabManager = self.main_widget.findChild(QTabWidget)
        tabManager.setCurrentIndex(1)

        self.system_combo.blockSignals(True)
        self.planet_combo.blockSignals(True)
        self.terminal_combo.blockSignals(True)

        system_id = trade_route["departure_system_id"] if is_buy else trade_route["arrival_system_id"]
        self.system_combo.setCurrentIndex(self.system_combo.findData(system_id))
        logger.info(f"Selected system ID: {system_id}")
        await self.update_planets()

        planet_id = trade_route["departure_planet_id"] if is_buy else trade_route["arrival_planet_id"]
        self.planet_combo.setCurrentIndex(self.planet_combo.findData(planet_id))
        logger.info(f"Selected planet ID: {planet_id}")

        terminal_id = trade_route["departure_terminal_id"] if is_buy else trade_route["arrival_terminal_id"]
        terminals = await self.update_terminals()
        if terminal_id in [terminal["id"] for terminal in terminals]:
            self.filter_terminals(terminal_id)
            logger.info(f"Selected terminal ID: {terminal_id}")
        else:
            logger.warning(f"Terminal ID {terminal_id} not found in the list of terminals")

        await self.update_commodities()

        commodity_list = self.commodity_buy_list if is_buy else self.commodity_sell_list
        commodity_id = trade_route["commodity_id"]
        for i in range(commodity_list.count()):
            item = commodity_list.item(i)
            if item.data(Qt.UserRole) == commodity_id:
                commodity_list.setCurrentItem(item)
                logger.info(f"Selected commodity ID: {commodity_id}")
                break

        self.quantity_input.setText(str(trade_route["max_buyable_scu"]))
        logger.info(f"Set quantity to: {trade_route['max_buyable_scu']}")

        self.terminal_combo.blockSignals(False)
        self.planet_combo.blockSignals(False)
        self.system_combo.blockSignals(False)

    def set_gui_enabled(self, enabled):
        for input in self.findChildren(QLineEdit):
            input.setEnabled(enabled)
        for combo in self.findChildren(QComboBox):
            combo.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)
        if enabled:
            self.update_buy_price(self.commodity_buy_list.currentItem(), self.commodity_buy_list.currentItem())
            self.update_sell_price(self.commodity_sell_list.currentItem(), self.commodity_sell_list.currentItem())
