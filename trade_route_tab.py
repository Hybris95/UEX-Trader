import logging
import sys
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox
from PyQt5.QtWidgets import (
    QPushButton, QTableWidget,
    QMessageBox, QTableWidgetItem,
    QHBoxLayout, QCheckBox,
    QProgressBar
)
from PyQt5.QtCore import Qt
import asyncio
from api import API
from config_manager import ConfigManager
from trade_tab import TradeTab
from translation_manager import TranslationManager
from tools import create_async_callback, days_difference_from_now


class TradeRouteTab(QWidget):
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.config_manager = None
        self.api = None
        self.translation_manager = None
        self.columns = None
        self.logger = logging.getLogger(__name__)
        self.terminals = []
        self.current_trades = []
        asyncio.ensure_future(self.load_systems())

    async def initialize(self):
        async with self._lock:
            if self.config_manager is None or self.translation_manager is None or self.api is None or self.columns is None:
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
        layout = QVBoxLayout()
        self.max_scu_input = QLineEdit()
        self.max_scu_input.setPlaceholderText(self.translation_manager.get_translation("enter",
                                                                                       self.config_manager.get_lang())
                                              + " " + self.translation_manager.get_translation("maximum",
                                                                                               self.config_manager.get_lang())
                                              + " " + self.translation_manager.get_translation("scu",
                                                                                               self.config_manager.get_lang()))
        layout.addWidget(QLabel(self.translation_manager.get_translation("maximum", self.config_manager.get_lang())
                                + " " + self.translation_manager.get_translation("scu", self.config_manager.get_lang())
                                + ":"))
        layout.addWidget(self.max_scu_input)
        self.max_investment_input = QLineEdit()
        self.max_investment_input.setPlaceholderText(self.translation_manager.get_translation("enter",
                                                                                              self.config_manager.get_lang())
                                                     + " "
                                                     + self.translation_manager.get_translation("maximum",
                                                                                                self.config_manager.get_lang())
                                                     + " "
                                                     + self.translation_manager.get_translation("investment",
                                                                                                self.config_manager.get_lang())
                                                     + " ("
                                                     + self.translation_manager.get_translation("uec",
                                                                                                self.config_manager.get_lang())
                                                     + ")")
        layout.addWidget(QLabel(self.translation_manager.get_translation("maximum",
                                                                         self.config_manager.get_lang())
                                + " "
                                + self.translation_manager.get_translation("investment",
                                                                           self.config_manager.get_lang())
                                + " ("
                                + self.translation_manager.get_translation("uec",
                                                                           self.config_manager.get_lang())
                                + "):"))
        layout.addWidget(self.max_investment_input)
        self.max_outdated_input = QLineEdit()
        self.max_outdated_input.setPlaceholderText(
            self.translation_manager.get_translation("enter",
                                                     self.config_manager.get_lang())
            + " "
            + self.translation_manager.get_translation("maximum",
                                                       self.config_manager.get_lang())
            + " "
            + self.translation_manager.get_translation("outdated",
                                                       self.config_manager.get_lang())
            + " ("
            + self.translation_manager.get_translation("days",
                                                       self.config_manager.get_lang())
            + ")")
        layout.addWidget(QLabel(self.translation_manager.get_translation("maximum",
                                                                         self.config_manager.get_lang())
                                + " "
                                + self.translation_manager.get_translation("outdated",
                                                                           self.config_manager.get_lang())
                                + " ("
                                + self.translation_manager.get_translation("days",
                                                                           self.config_manager.get_lang())
                                + "):"))
        layout.addWidget(self.max_outdated_input)
        self.min_trade_profit_input = QLineEdit()
        self.min_trade_profit_input.setPlaceholderText(
            self.translation_manager.get_translation("enter",
                                                     self.config_manager.get_lang())
            + " "
            + self.translation_manager.get_translation("minimum",
                                                       self.config_manager.get_lang())
            + " "
            + self.translation_manager.get_translation("trade_columns_total_margin",
                                                       self.config_manager.get_lang())
            + " ("
            + self.translation_manager.get_translation("uec",
                                                       self.config_manager.get_lang())
            + ")")
        self.min_trade_profit_input.setText("8000")
        layout.addWidget(QLabel(self.translation_manager.get_translation("minimum",
                                                                         self.config_manager.get_lang())
                                + " "
                                + self.translation_manager.get_translation("trade_columns_total_margin",
                                                                           self.config_manager.get_lang())
                                + " ("
                                + self.translation_manager.get_translation("uec",
                                                                           self.config_manager.get_lang())
                                + "):"))
        layout.addWidget(self.min_trade_profit_input)
        self.departure_system_combo = QComboBox()
        self.departure_system_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_planets()))
        layout.addWidget(QLabel(self.translation_manager.get_translation("departure_system",
                                                                         self.config_manager.get_lang())
                                + ":"))
        layout.addWidget(self.departure_system_combo)
        self.departure_planet_combo = QComboBox()
        self.departure_planet_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_terminals()))
        layout.addWidget(QLabel(self.translation_manager.get_translation("departure_planet",
                                                                         self.config_manager.get_lang())
                                + ":"))
        layout.addWidget(self.departure_planet_combo)
        terminal_label = QLabel(self.translation_manager.get_translation("select_terminal",
                                                                         self.config_manager.get_lang())
                                + ":")
        self.terminal_filter_input = QLineEdit()
        self.terminal_filter_input.setPlaceholderText(self.translation_manager.get_translation("filter_terminals",
                                                                                               self.config_manager.get_lang()))
        self.terminal_filter_input.textChanged.connect(self.filter_terminals)
        self.departure_terminal_combo = QComboBox()
        layout.addWidget(terminal_label)
        layout.addWidget(self.terminal_filter_input)
        layout.addWidget(self.departure_terminal_combo)
        # Add checkboxes for filtering
        self.filter_system_checkbox = QCheckBox(self.translation_manager.get_translation("filter_for_current_system",
                                                                                         self.config_manager.get_lang()))
        self.filter_system_checkbox.setChecked(True)  # Ensure this checkbox is checked by default
        self.filter_planet_checkbox = QCheckBox(self.translation_manager.get_translation("filter_for_current_planet",
                                                                                         self.config_manager.get_lang()))
        layout.addWidget(self.filter_system_checkbox)
        layout.addWidget(self.filter_planet_checkbox)
        # Add checkboxes for ignoring stocks and demand
        self.ignore_stocks_checkbox = QCheckBox(self.translation_manager.get_translation("ignore_stocks",
                                                                                         self.config_manager.get_lang()))
        self.ignore_demand_checkbox = QCheckBox(self.translation_manager.get_translation("ignore_demand",
                                                                                         self.config_manager.get_lang()))
        layout.addWidget(self.ignore_stocks_checkbox)
        layout.addWidget(self.ignore_demand_checkbox)
        self.filter_public_hangars_checkbox = QCheckBox(self.translation_manager.get_translation("no_public_hangars",
                                                                                                 self.config_manager.
                                                                                                 get_lang()))
        layout.addWidget(self.filter_public_hangars_checkbox)
        self.filter_space_only_checkbox = QCheckBox(self.translation_manager.get_translation("space_only",
                                                                                             self.config_manager.get_lang()))
        layout.addWidget(self.filter_space_only_checkbox)

        self.find_route_button = QPushButton(self.translation_manager.get_translation("find_trade_route",
                                                                                      self.config_manager.get_lang()))
        self.find_route_button.clicked.connect(lambda: asyncio.ensure_future(self.find_trade_routes()))
        layout.addWidget(self.find_route_button)

        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.main_progress_bar)
        layout.addWidget(self.progress_bar)

        self.page_items_combo = QComboBox()
        self.page_items_combo.addItem("10 " + self.translation_manager.get_translation("maximum_results",
                                                                                       self.config_manager.get_lang()), 10)
        self.page_items_combo.addItem("20 " + self.translation_manager.get_translation("maximum_results",
                                                                                       self.config_manager.get_lang()), 20)
        self.page_items_combo.addItem("50 " + self.translation_manager.get_translation("maximum_results",
                                                                                       self.config_manager.get_lang()), 50)
        self.page_items_combo.addItem("100 " + self.translation_manager.get_translation("maximum_results",
                                                                                        self.config_manager.get_lang()), 100)
        self.page_items_combo.addItem("500 " + self.translation_manager.get_translation("maximum_results",
                                                                                        self.config_manager.get_lang()), 500)
        self.page_items_combo.addItem("1000 " + self.translation_manager.get_translation("maximum_results",
                                                                                         self.config_manager.get_lang()), 1000)
        self.page_items_combo.setCurrentIndex(0)
        self.page_items_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_page_items())
        )
        layout.addWidget(self.page_items_combo)

        self.sorting_options_combo = QComboBox()
        self.sorting_options_combo.addItem(self.translation_manager.get_translation("sort_trade_margin",
                                                                                    self.config_manager.get_lang())
                                           + " ("
                                           + self.translation_manager.get_translation("uec",
                                                                                      self.config_manager.get_lang())
                                           + ")", "total_margin")
        self.sorting_options_combo.addItem(self.translation_manager.get_translation("sort_profit_margin",
                                                                                    self.config_manager.get_lang())
                                           + " (%)", "profit_margin")
        self.sorting_options_combo.addItem(self.translation_manager.get_translation("sort_scu_margin",
                                                                                    self.config_manager.get_lang())
                                           + " ("
                                           + self.translation_manager.get_translation("uec",
                                                                                      self.config_manager.get_lang())
                                           + "/"
                                           + self.translation_manager.get_translation("scu",
                                                                                      self.config_manager.get_lang())
                                           + ")", "unit_margin")
        self.sorting_options_combo.addItem(self.translation_manager.get_translation("trade_columns_investment",
                                                                                    self.config_manager.get_lang())
                                           + " ("
                                           + self.translation_manager.get_translation("uec",
                                                                                      self.config_manager.get_lang())
                                           + ")", "investment")
        self.sorting_options_combo.addItem(self.translation_manager.get_translation("trade_columns_buy_scu",
                                                                                    self.config_manager.get_lang())
                                           + " ("
                                           + self.translation_manager.get_translation("unit_qty",
                                                                                      self.config_manager.get_lang())
                                           + ")", "buy_scu")
        self.sorting_options_combo.addItem(self.translation_manager.get_translation("total_margin_by_distance",
                                                                                    self.config_manager.get_lang())
                                           + " ("
                                           + self.translation_manager.get_translation("uec",
                                                                                      self.config_manager.get_lang())
                                           + "/"
                                           + self.translation_manager.get_translation("km",
                                                                                      self.config_manager.get_lang())
                                           + ")", "total_margin_by_distance")
        self.sorting_options_combo.addItem(self.translation_manager.get_translation("unit_margin_by_distance",
                                                                                    self.config_manager.get_lang())
                                           + " ("
                                           + self.translation_manager.get_translation("uec",
                                                                                      self.config_manager.get_lang())
                                           + "/"
                                           + self.translation_manager.get_translation("scu",
                                                                                      self.config_manager.get_lang())
                                           + "/"
                                           + self.translation_manager.get_translation("km",
                                                                                      self.config_manager.get_lang())
                                           + ")", "unit_margin_by_distance")
        self.sorting_options_combo.setCurrentIndex(0)
        self.sorting_options_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_page_items())
        )
        layout.addWidget(self.sorting_options_combo)

        self.sorting_order_combo = QComboBox()
        self.sorting_order_combo.addItem(self.translation_manager.get_translation("sort_descending",
                                                                                  self.config_manager.get_lang()),
                                         "DESC")
        self.sorting_order_combo.addItem(self.translation_manager.get_translation("sort_ascending",
                                                                                  self.config_manager.get_lang()),
                                         "ASC")
        self.sorting_order_combo.setCurrentIndex(0)
        self.sorting_order_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_page_items())
        )
        layout.addWidget(self.sorting_order_combo)

        self.trade_route_table = QTableWidget()
        layout.addWidget(self.trade_route_table)
        self.setLayout(layout)
        self.define_columns()

    async def load_systems(self):
        try:
            await self.ensure_initialized()
            systems = await self.api.fetch_data("/star_systems")
            for system in systems.get("data", []):
                if system.get("is_available") == 1:
                    self.departure_system_combo.addItem(system["name"], system["id"])
            logging.info("Systems loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load systems: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_systems",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_planets(self):
        await self.ensure_initialized()
        self.departure_planet_combo.clear()
        self.departure_terminal_combo.clear()
        self.terminal_filter_input.clear()  # Clear the filter input here
        self.terminals = []
        system_id = self.departure_system_combo.currentData()
        if not system_id:
            return
        try:
            planets = await self.api.fetch_data("/planets", params={'id_star_system': system_id})
            for planet in planets.get("data", []):
                self.departure_planet_combo.addItem(planet["name"], planet["id"])
            logging.info("Planets loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load planets: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_planets",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_terminals(self):
        await self.ensure_initialized()
        self.departure_terminal_combo.clear()
        self.terminal_filter_input.clear()  # Ensure the filter input is cleared when updating terminals
        self.terminals = []
        planet_id = self.departure_planet_combo.currentData()
        if not planet_id:
            return
        try:
            terminals = await self.api.fetch_data("/terminals", params={'id_planet': planet_id})
            self.terminals = [terminal for terminal in terminals.get("data", [])
                              if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
            self.filter_terminals()
            logging.info("Terminals loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load terminals: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_terminals",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_page_items(self):
        await self.ensure_initialized()
        await self.update_trade_route_table(self.current_trades, self.columns, quick=False)

    def filter_terminals(self):
        filter_text = self.terminal_filter_input.text().lower()
        self.departure_terminal_combo.clear()
        for terminal in self.terminals:
            if filter_text in terminal["name"].lower():
                self.departure_terminal_combo.addItem(terminal["name"], terminal["id"])

    def define_columns(self):
        self.columns = [
            self.translation_manager.get_translation("trade_columns_destination", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_commodity", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_buy_scu", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_buy_price", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_sell_price", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_investment", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_unit_margin", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_total_margin", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_departure_scu_available", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_arrival_demand_scu", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_profit_margin", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_arrival_terminal_mcs", self.config_manager.get_lang()),
            self.translation_manager.get_translation("trade_columns_actions", self.config_manager.get_lang())
        ]
        self.trade_route_table.setColumnCount(len(self.columns))
        self.trade_route_table.setHorizontalHeaderLabels(self.columns)

    async def find_trade_routes(self):
        await self.ensure_initialized()
        self.logger.log(logging.INFO, "Searching for a new Trade Route")
        self.trade_route_table.setRowCount(0)  # Clear previous results

        await self.main_widget.set_gui_enabled(False)
        self.main_progress_bar.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.main_progress_bar.setValue(0)

        try:
            (max_scu,
             max_investment,
             max_outdated_days,
             min_trade_profit,
             departure_system_id,
             departure_planet_id,
             departure_terminal_id
             ) = self.validate_inputs()
            if not all([departure_system_id, departure_planet_id, departure_terminal_id]):
                QMessageBox.warning(self, self.translation_manager.get_translation("error_input_error",
                                                                                   self.config_manager.get_lang()),
                                    self.translation_manager.get_translation("error_input_select_dpt",
                                                                             self.config_manager.get_lang()))
                return

            self.current_trades = await self.fetch_and_process_departure_commodities(
                departure_terminal_id,
                max_scu,
                max_investment,
                max_outdated_days,
                min_trade_profit,
                departure_system_id,
                departure_planet_id
            )

            await self.update_trade_route_table(self.current_trades, self.columns, quick=False)
        except Exception as e:
            self.logger.log(logging.ERROR, f"An error occurred while finding trade routes: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_generic",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")
        finally:
            await self.main_widget.set_gui_enabled(True)
            self.progress_bar.setVisible(False)
            self.main_progress_bar.setVisible(False)

    def validate_inputs(self):
        max_scu = int(self.max_scu_input.text()) if self.max_scu_input.text() else sys.maxsize
        max_investment = float(self.max_investment_input.text()) if self.max_investment_input.text() else sys.maxsize
        max_outdated_days = int(self.max_outdated_input.text()) if self.max_outdated_input.text() else sys.maxsize
        min_trade_profit = int(self.min_trade_profit_input.text()) if self.min_trade_profit_input.text() else 0
        departure_system_id = self.departure_system_combo.currentData()
        departure_planet_id = self.departure_planet_combo.currentData()
        departure_terminal_id = self.departure_terminal_combo.currentData()
        return (max_scu,
                max_investment,
                max_outdated_days,
                min_trade_profit,
                departure_system_id,
                departure_planet_id,
                departure_terminal_id)

    async def fetch_and_process_departure_commodities(
        self,
        departure_terminal_id,
        max_scu,
        max_investment,
        max_outdated_days,
        min_trade_profit,
        departure_system_id,
        departure_planet_id
    ):
        await self.ensure_initialized()
        trade_routes = []
        departure_commodities = await self.api.fetch_data(
            "/commodities_prices", params={'id_terminal': departure_terminal_id}
        )
        self.logger.log(
            logging.INFO,
            f"Iterating through {len(departure_commodities.get('data', []))} commodities at departure terminal"
        )
        universe = len(departure_commodities.get("data", []))
        self.main_progress_bar.setMaximum(universe)
        actionProgress = 0
        for departure_commodity in departure_commodities.get("data", []):
            self.main_progress_bar.setValue(actionProgress)
            actionProgress += 1
            if departure_commodity.get("price_buy") == 0:
                continue
            arrival_commodities = await self.api.fetch_data(
                "/commodities_prices",
                params={'id_commodity': departure_commodity.get("id_commodity")}
            )
            self.logger.log(
                logging.INFO,
                f"Found {len(arrival_commodities.get('data', []))} terminals that might sell "
                f"{departure_commodity.get('commodity_name')}"
            )
            trade_routes.extend(await self.process_arrival_commodities(
                arrival_commodities, departure_commodity, max_scu, max_investment,
                max_outdated_days, min_trade_profit,
                departure_system_id, departure_planet_id, departure_terminal_id
            ))
            await self.update_trade_route_table(trade_routes, self.columns)
        self.main_progress_bar.setValue(actionProgress)
        return trade_routes

    async def process_arrival_commodities(
        self, arrival_commodities, departure_commodity, max_scu, max_investment, max_outdated_days,
        min_trade_profit, departure_system_id, departure_planet_id, departure_terminal_id
    ):
        await self.ensure_initialized()
        arrival_commodities = arrival_commodities.get("data", [])
        trade_routes = []
        universe = len(arrival_commodities)
        self.progress_bar.setMaximum(universe)
        actionProgress = 0
        for arrival_commodity in arrival_commodities:
            self.progress_bar.setValue(actionProgress)
            actionProgress += 1
            if arrival_commodity.get("is_available") == 0 or arrival_commodity.get("id_terminal") == departure_terminal_id:
                continue
            if self.filter_system_checkbox.isChecked() and arrival_commodity.get("id_star_system") != departure_system_id:
                continue
            if self.filter_planet_checkbox.isChecked() and arrival_commodity.get("id_planet") != departure_planet_id:
                continue
            if self.filter_public_hangars_checkbox.isChecked() and (not arrival_commodity["city_name"]
                                                                    and not arrival_commodity["space_station_name"]):
                continue
            if self.filter_space_only_checkbox.isChecked() and not arrival_commodity["space_station_name"]:
                continue
            trade_route = await self.calculate_trade_route_details(
                arrival_commodity, departure_commodity, max_scu, max_investment, max_outdated_days,
                min_trade_profit, departure_system_id, departure_planet_id, departure_terminal_id
            )
            if trade_route:
                trade_routes.append(trade_route)
        self.progress_bar.setValue(actionProgress)
        return trade_routes

    async def calculate_trade_route_details(
        self, arrival_commodity, departure_commodity, max_scu, max_investment, max_outdated_days,
        min_trade_profit, departure_system_id, departure_planet_id, departure_terminal_id
    ):
        await self.ensure_initialized()
        buy_price = departure_commodity.get("price_buy", 0)
        available_scu = departure_commodity.get("scu_buy", 0)
        original_available_scu = available_scu  # Store original available SCU
        scu_sell_stock = arrival_commodity.get("scu_sell_stock", 0)
        scu_sell_users = arrival_commodity.get("scu_sell_users", 0)
        sell_price = arrival_commodity.get("price_sell", 0)
        demand_scu = scu_sell_stock - scu_sell_users
        original_demand_scu = demand_scu  # Store original demand SCU
        if self.ignore_stocks_checkbox.isChecked():
            available_scu = max_scu
        if self.ignore_demand_checkbox.isChecked():
            demand_scu = max_scu
        if not buy_price or not sell_price or available_scu <= 0 or not demand_scu:
            return None
        max_buyable_scu = min(max_scu, available_scu, int(max_investment // buy_price), demand_scu)
        if max_buyable_scu <= 0:
            return None
        buy_update = departure_commodity["date_modified"]
        sell_update = arrival_commodity["date_modified"]
        sell_update_days = days_difference_from_now(sell_update)
        if (sell_update_days > max_outdated_days):
            return None
        investment = buy_price * max_buyable_scu
        unit_margin = (sell_price - buy_price)
        total_margin = unit_margin * max_buyable_scu
        if (total_margin <= 0) or (total_margin < min_trade_profit):
            return None
        profit_margin = unit_margin / buy_price
        arrival_terminal = await self.api.fetch_data("/terminals", params={'id': arrival_commodity.get("id_terminal")})
        arrival_terminal_mcs = arrival_terminal.get("data")[0].get("mcs")
        arrival_id_star_system = arrival_commodity.get("id_star_system")
        destination = next(
            (system["name"] for system in (await self.api.fetch_data("/star_systems")).get("data", [])
             if system["id"] == arrival_id_star_system),
            "Unknown System"
        ) + " - " + next(
            (planet["name"] for planet in (await self.api.fetch_data(
                "/planets", params={'id_star_system': arrival_id_star_system}
            )).get("data", [])
             if planet["id"] == arrival_commodity.get("id_planet")),
            "Unknown Planet"
        ) + " / " + arrival_commodity.get("terminal_name")
        distance = await self.api.fetch_distance(departure_commodity["id_terminal"],
                                                 arrival_commodity["id_terminal"],
                                                 departure_commodity["id_commodity"])
        total_margin_by_distance = total_margin / distance
        unit_margin_by_distance = unit_margin / distance
        return {
            "destination": destination,
            "commodity": departure_commodity.get("commodity_name"),
            "buy_scu": str(max_buyable_scu) + " "
            + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),
            "buy_price": str(buy_price) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "sell_price": str(sell_price) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "investment": str(investment) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "unit_margin": str(unit_margin) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "total_margin": str(total_margin) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "departure_scu_available": str(original_available_scu) + " "
            + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),  # Show original available SCU
            "arrival_demand_scu": str(original_demand_scu) + " "
            + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),  # Show original demand SCU
            "profit_margin": str(round(profit_margin * 100)) + " %",
            "arrival_terminal_mcs": arrival_terminal_mcs,
            "departure_system_id": departure_system_id,
            "departure_planet_id": departure_planet_id,
            "departure_terminal_id": departure_terminal_id,
            "arrival_system_id": arrival_commodity.get("id_star_system"),
            "arrival_planet_id": arrival_commodity.get("id_planet"),
            "arrival_terminal_id": arrival_commodity.get("id_terminal"),
            "commodity_id": departure_commodity.get("id_commodity"),
            "max_buyable_scu": max_buyable_scu,
            "buy_latest_update": str(departure_commodity["date_modified"]),
            "sell_latest_update": str(departure_commodity["date_modified"]),
            "oldest_update": str(buy_update) if buy_update < sell_update else str(sell_update),
            "latest_update": str(buy_update) if buy_update > sell_update else str(sell_update),
            "distance": distance,
            "total_margin_by_distance": str(total_margin_by_distance),
            "unit_margin_by_distance": str(unit_margin_by_distance)
        }

    async def update_trade_route_table(self, trade_routes, columns, quick=True):
        await self.ensure_initialized()
        sorting_formula = self.sorting_options_combo.currentData()
        reverse_order = True if self.sorting_order_combo.currentData() == "DESC" else False
        nb_items = 5 if quick else self.page_items_combo.currentData()
        trade_routes.sort(key=lambda x: float(x[sorting_formula].split()[0]), reverse=reverse_order)
        self.trade_route_table.setRowCount(0)  # Clear the table before adding sorted results
        for i, route in enumerate(trade_routes[:nb_items]):
            self.trade_route_table.insertRow(i)
            for j, value in enumerate(route.values()):
                if j < len(columns) - 1:
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the item non-editable
                    self.trade_route_table.setItem(i, j, item)
                else:
                    action_layout = QHBoxLayout()
                    buy_button = QPushButton(self.translation_manager.get_translation("select_to_buy",
                                                                                      self.config_manager.get_lang()))
                    buy_button.clicked.connect(create_async_callback(self.select_to_buy, trade_routes[i]))
                    sell_button = QPushButton(self.translation_manager.get_translation("select_to_sell",
                                                                                       self.config_manager.get_lang()))
                    sell_button.clicked.connect(create_async_callback(self.select_to_sell, trade_routes[i]))
                    action_layout.addWidget(buy_button)
                    action_layout.addWidget(sell_button)
                    action_widget = QWidget()
                    action_widget.setLayout(action_layout)
                    self.trade_route_table.setCellWidget(i, j, action_widget)
        if len(trade_routes) == 0:
            self.trade_route_table.insertRow(0)
            item = QTableWidgetItem(self.translation_manager.get_translation("no_results_found",
                                                                             self.config_manager.get_lang()))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the item non-editable
            self.trade_route_table.setItem(0, 0, item)
        self.trade_route_table.resizeColumnsToContents()
        self.logger.log(logging.INFO, "Finished calculating Trade routes")

    async def select_to_buy(self, trade_route):
        await self.ensure_initialized()
        self.logger.log(logging.INFO, "Selected route to buy")
        trade_tab = self.main_widget.findChild(TradeTab)
        if trade_tab:
            self.main_widget.loop.create_task(trade_tab.select_trade_route(trade_route, is_buy=True))
        else:
            self.logger.log(logging.ERROR, "An error occurred while selecting trade route")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_generic",
                                                                          self.config_manager.get_lang()))

    async def select_to_sell(self, trade_route):
        await self.ensure_initialized()
        self.logger.log(logging.INFO, "Selected route to sell")
        trade_tab = self.main_widget.findChild(TradeTab)
        if trade_tab:
            self.main_widget.loop.create_task(trade_tab.select_trade_route(trade_route, is_buy=False))
        else:
            self.logger.log(logging.ERROR, "An error occurred while selecting trade route")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_generic",
                                                                          self.config_manager.get_lang()))

    def set_gui_enabled(self, enabled):
        for input in self.findChildren(QLineEdit):
            input.setEnabled(enabled)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.setEnabled(enabled)
        for combo in self.findChildren(QComboBox):
            combo.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)
