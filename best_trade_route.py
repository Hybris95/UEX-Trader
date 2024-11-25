import logging
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QMessageBox, QTableWidgetItem,
    QHBoxLayout, QCheckBox, QApplication, QProgressBar
)
from PyQt5.QtCore import Qt
import asyncio
from api import API
from config_manager import ConfigManager
from trade_tab import TradeTab
from translation_manager import TranslationManager
from tools import create_async_callback, days_difference_from_now


class BestTradeRouteTab(QWidget):
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
                if ConfigManager._instance is None:
                    self.config_manager = ConfigManager()
                    await self.config_manager.initialize()
                else:
                    self.config_manager = ConfigManager._instance
                if TranslationManager._instance is None:
                    self.translation_manager = TranslationManager()
                    await self.translation_manager.initialize()
                else:
                    self.translation_manager = TranslationManager._instance
                if API._instance is None:
                    self.api = API(self.config_manager)
                    await self.api.initialize()
                else:
                    self.api = API._instance
                self.columns = [
                    self.translation_manager.get_translation("trade_columns_departure", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_destination", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_commodity", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_buy_scu", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_buy_price", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_sell_price", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_investment", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_unit_margin", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_total_margin", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_departure_scu_available",
                                                             self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_arrival_demand_scu",
                                                             self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_profit_margin", self.config_manager.get_lang()),
                    self.translation_manager.get_translation("trade_columns_actions", self.config_manager.get_lang())
                ]
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
            + ") - "
            + self.translation_manager.get_translation("not_user_trades",
                                                       self.config_manager.get_lang())
            )
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
        self.departure_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_departure_planets())
        )
        layout.addWidget(QLabel(self.translation_manager.get_translation("departure_system",
                                                                         self.config_manager.get_lang())
                                + ":"))
        layout.addWidget(self.departure_system_combo)
        self.departure_planet_combo = QComboBox()
        self.departure_planet_combo.addItem(self.translation_manager.get_translation("all_planets",
                                                                                     self.config_manager.get_lang()),
                                            "all_planets")
        self.departure_planet_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_departure_terminals())
        )
        layout.addWidget(QLabel(self.translation_manager.get_translation("departure_planet",
                                                                         self.config_manager.get_lang())
                                + ":"))
        layout.addWidget(self.departure_planet_combo)
        self.destination_system_combo = QComboBox()
        self.destination_system_combo.addItem(self.translation_manager.get_translation("all_systems",
                                                                                       self.config_manager.get_lang()),
                                              "all_systems")
        self.destination_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_destination_planets())
        )
        layout.addWidget(QLabel(self.translation_manager.get_translation("destination_system",
                                                                         self.config_manager.get_lang())
                                + ":"))
        layout.addWidget(self.destination_system_combo)
        self.destination_planet_combo = QComboBox()
        self.destination_planet_combo.addItem(self.translation_manager.get_translation("all_planets",
                                                                                       self.config_manager.get_lang()),
                                              "all_planets")
        self.destination_planet_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_destination_terminals())
        )
        layout.addWidget(QLabel(self.translation_manager.get_translation("destination_planet",
                                                                         self.config_manager.get_lang())
                                + ":"))
        layout.addWidget(self.destination_planet_combo)
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

        self.find_route_button_rework = QPushButton(self.translation_manager.get_translation("find_best_trade_routes",
                                                                                             self.config_manager.get_lang()))
        self.find_route_button_rework.clicked.connect(lambda: asyncio.ensure_future(self.find_best_trade_routes_rework()))
        layout.addWidget(self.find_route_button_rework)

        self.find_route_button_users = QPushButton(self.translation_manager.get_translation("find_best_trade_from_user",
                                                                                            self.config_manager.get_lang()))
        self.find_route_button_users.clicked.connect(lambda: asyncio.ensure_future(self.find_best_trade_routes_users()))
        layout.addWidget(self.find_route_button_users)

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

    async def load_systems(self):
        try:
            await self.ensure_initialized()
            systems = await self.api.fetch_data("/star_systems")
            for system in systems.get("data", []):
                if system.get("is_available") == 1:
                    self.departure_system_combo.addItem(system["name"], system["id"])
                    self.destination_system_combo.addItem(system["name"], system["id"])
            logging.info("Systems loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load systems: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_systems",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_departure_planets(self):
        await self.ensure_initialized()
        self.departure_planet_combo.clear()
        self.departure_planet_combo.addItem(self.translation_manager.get_translation("all_planets",
                                                                                     self.config_manager.get_lang()),
                                            "all_planets")
        self.terminals = []
        system_id = self.departure_system_combo.currentData()
        if not system_id:
            return
        try:
            planets = await self.api.fetch_data("/planets", params={'id_star_system': system_id})
            for planet in planets.get("data", []):
                self.departure_planet_combo.addItem(planet["name"], planet["id"])
            logging.info("Departure planets loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load departure planets: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_departure_planets",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_departure_terminals(self):
        await self.ensure_initialized()
        self.terminals = []
        planet_id = self.departure_planet_combo.currentData()
        if not planet_id and self.departure_planet_combo.currentData() != "all_planets":
            return
        try:
            params = {'id_star_system': self.departure_system_combo.currentData()}
            if self.departure_planet_combo.currentData() != "all_planets":
                params['id_planet'] = planet_id
            terminals = await self.api.fetch_data("/terminals", params=params)
            self.terminals = [terminal for terminal in terminals.get("data", [])
                              if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
            logging.info("Departure terminals loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load departure terminals: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_departure_terminals",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_destination_planets(self):
        await self.ensure_initialized()
        self.destination_planet_combo.clear()
        self.destination_planet_combo.addItem(self.translation_manager.get_translation("all_planets",
                                                                                       self.config_manager.get_lang()),
                                              "all_planets")
        system_id = self.destination_system_combo.currentData()
        if not system_id and self.destination_system_combo.currentData() != "all_systems":
            return
        try:
            params = {}
            if self.destination_system_combo.currentData() != "all_systems":
                params['id_star_system'] = system_id
            planets = await self.api.fetch_data("/planets", params=params)
            for planet in planets.get("data", []):
                self.destination_planet_combo.addItem(planet["name"], planet["id"])
            logging.info("Destination planets loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load destination planets: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_destination_planets",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_destination_terminals(self):
        await self.ensure_initialized()
        self.destination_terminals = []
        planet_id = self.destination_planet_combo.currentData()
        if not planet_id and self.destination_planet_combo.currentData() != "all_planets":
            return
        try:
            params = {}
            if self.destination_system_combo.currentData() != "all_systems":
                params['id_star_system'] = self.destination_system_combo.currentData()
            if self.destination_planet_combo.currentData() != "all_planets":
                params['id_planet'] = planet_id
            terminals = await self.api.fetch_data("/terminals", params=params)
            self.destination_terminals = [terminal for terminal in terminals.get("data", [])
                                          if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
            logging.info("Destination terminals loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load destination terminals: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_failed_to_load_destination_terminals",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")

    async def update_page_items(self):
        await self.ensure_initialized()
        await self.display_trade_routes(self.current_trades, self.columns, quick=False)

    async def find_best_trade_routes_users(self):
        await self.ensure_initialized()
        self.logger.log(logging.INFO, "Searching for Best Trade Routes")
        self.trade_route_table.setRowCount(0)  # Clear previous results
        self.trade_route_table.setColumnCount(len(self.columns))
        self.trade_route_table.setHorizontalHeaderLabels(self.columns)
        await self.main_widget.set_gui_enabled(False)
        self.main_progress_bar.setVisible(True)
        self.progress_bar.setVisible(True)
        currentProgress = 0
        self.progress_bar.setValue(currentProgress)
        self.main_progress_bar.setValue(currentProgress)
        self.main_progress_bar.setMaximum(5)

        try:
            max_scu, max_investment, max_outdated_in_days, min_trade_profit = self.get_input_values()
            departure_system_id, departure_planet_id, destination_system_id, destination_planet_id = self.get_selected_ids()

            if not departure_system_id:
                QMessageBox.warning(self, self.translation_manager.get_translation("error_input_error",
                                                                                   self.config_manager.get_lang()),
                                    self.translation_manager.get_translation("error_input_select_ds",
                                                                             self.config_manager.get_lang()))
                return

            departure_planets = []
            if not departure_planet_id:
                departure_planets = await self.api.fetch_planets(departure_system_id)
            else:
                departure_planets = await self.api.fetch_planets(departure_system_id, departure_planet_id)
            self.logger.log(logging.INFO, f"{len(departure_planets)} departure planets found")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            destination_systems = []
            if not destination_system_id:
                destination_systems = await self.api.fetch_systems_from_origin_system(departure_system_id, 2)
            else:
                destination_systems = await self.api.fetch_system(destination_system_id)
            self.logger.log(logging.INFO, f"{len(destination_systems)} destination systems found")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            destination_planets = []
            universe = len(destination_systems)
            self.progress_bar.setMaximum(universe)
            actionProgress = 0
            for destination_system in destination_systems:
                if not destination_planet_id:
                    destination_planets.extend(await self.api.fetch_planets(destination_system["id"]))
                else:
                    destination_planets.extend(await self.api.fetch_planets(destination_system["id"], destination_planet_id))
                actionProgress += 1
                self.progress_bar.setValue(actionProgress)
            self.logger.log(logging.INFO, f"{len(destination_planets)} destination planets found")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            commodities_routes = []
            universe = len(departure_planets) * len(destination_planets)
            self.progress_bar.setMaximum(universe)
            actionProgress = 0
            for departure_planet in departure_planets:
                for destination_planet in destination_planets:
                    commodities_routes.extend(await self.api.fetch_routes(departure_planet["id"], destination_planet["id"]))
                    actionProgress += 1
                    self.progress_bar.setValue(actionProgress)
            self.logger.log(logging.INFO, f"{len(commodities_routes)} commodities routes to parse")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            self.current_trades = await self.calculate_trade_routes_users(commodities_routes,
                                                                          max_scu,
                                                                          max_investment,
                                                                          min_trade_profit)
            self.logger.log(logging.INFO, f"{len(self.current_trades)} routes found")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)
            self.logger.log(logging.INFO, "Finished calculating Best Trade Routes")

        except Exception as e:
            self.logger.log(logging.ERROR, f"An error occurred while finding best trade routes: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_generic",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")
        finally:
            await self.main_widget.set_gui_enabled(True)
            self.main_progress_bar.setVisible(False)
            self.progress_bar.setVisible(False)

    async def find_best_trade_routes_rework(self):
        await self.ensure_initialized()
        self.logger.log(logging.INFO, "Searching for Best Trade Routes")
        self.trade_route_table.setRowCount(0)  # Clear previous results
        self.trade_route_table.setColumnCount(len(self.columns))
        self.trade_route_table.setHorizontalHeaderLabels(self.columns)
        await self.main_widget.set_gui_enabled(False)
        self.main_progress_bar.setVisible(True)
        self.progress_bar.setVisible(True)
        currentProgress = 0
        self.progress_bar.setValue(currentProgress)
        self.main_progress_bar.setValue(currentProgress)
        self.main_progress_bar.setMaximum(7)

        try:
            # [Recover entry parameters]
            max_scu, max_investment, max_outdated_in_days, min_trade_profit = self.get_input_values()
            departure_system_id, departure_planet_id, destination_system_id, destination_planet_id = self.get_selected_ids()
            ignore_stocks = self.ignore_stocks_checkbox.isChecked()
            ignore_demand = self.ignore_demand_checkbox.isChecked()
            filter_public_hangars = self.filter_public_hangars_checkbox.isChecked()
            filter_space_only = self.filter_space_only_checkbox.isChecked()

            if not departure_system_id:
                QMessageBox.warning(self, self.translation_manager.get_translation("error_input_error",
                                                                                   self.config_manager.get_lang()),
                                    self.translation_manager.get_translation("error_input_select_ds",
                                                                             self.config_manager.get_lang()))
                return

            # [Recover departure/destination planets]
            departure_planets = []
            if not departure_planet_id:
                departure_planets = await self.api.fetch_planets(departure_system_id)
                self.logger.log(logging.INFO, f"{len(departure_planets)} Departure Planets found.")
            else:
                departure_planets = await self.api.fetch_planets(departure_system_id, departure_planet_id)
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            destination_systems = []
            if not destination_system_id:
                destination_systems = await self.api.fetch_systems_from_origin_system(departure_system_id, max_bounce=2)
                self.logger.log(logging.INFO, f"{len(destination_systems)} Destination Systems found.")
            else:
                destination_systems = await self.api.fetch_system(destination_system_id)
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            destination_planets = []
            universe = len(destination_systems)
            self.progress_bar.setMaximum(universe)
            actionProgress = 0
            if not destination_planet_id:
                for destination_system in destination_systems:
                    destination_planets.extend(await self.api.fetch_planets(destination_system["id"]))
                    actionProgress += 1
                    self.progress_bar.setValue(actionProgress)
                self.logger.log(logging.INFO, f"{len(destination_planets)} Destination Planets found.")
            else:
                destination_planets = await self.api.fetch_planets(destination_system_id, destination_planet_id)
                actionProgress += 1
                self.progress_bar.setValue(actionProgress)
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            # [Recover departure/destination terminals and commodities]
            departure_terminals = await self.get_terminals_from_planets(departure_planets,
                                                                        filter_public_hangars,
                                                                        filter_space_only)
            self.logger.log(logging.INFO, f"{len(departure_terminals)} Departure Terminals found.")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            buy_commodities = await self.get_buy_commodities_from_terminals(departure_terminals)
            self.logger.log(logging.INFO, f"{len(buy_commodities)} Buy Commodities found.")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            sell_commodities = await self.get_sell_commodities_from_commodities_prices(buy_commodities,
                                                                                       filter_public_hangars,
                                                                                       filter_space_only)
            self.logger.log(logging.INFO, f"{len(sell_commodities)} Sell Commodities found.")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            self.current_trades = await self.calculate_trade_routes_rework(buy_commodities, sell_commodities,
                                                                           max_scu, max_investment,
                                                                           ignore_stocks, ignore_demand,
                                                                           max_outdated_in_days, min_trade_profit)
            self.logger.log(logging.INFO, f"{len(self.current_trades)} Trade routes found.")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)
            self.logger.log(logging.INFO, f"Finished calculating Best Trade Routes : {len(self.current_trades)} found")
        except Exception as e:
            self.logger.log(logging.ERROR, f"An error occurred while finding best trade routes: {e}")
            QMessageBox.critical(self, self.translation_manager.get_translation("error_error",
                                                                                self.config_manager.get_lang()),
                                 self.translation_manager.get_translation("error_generic",
                                                                          self.config_manager.get_lang())
                                 + f": {e}")
        finally:
            await self.main_widget.set_gui_enabled(True)
            self.progress_bar.setVisible(False)
            self.main_progress_bar.setVisible(False)

    def get_input_values(self):
        max_scu = int(self.max_scu_input.text()) if self.max_scu_input.text() else sys.maxsize
        max_investment = float(self.max_investment_input.text()) if self.max_investment_input.text() else sys.maxsize
        max_outdated_in_days = int(self.max_outdated_input.text()) if self.max_outdated_input.text() else sys.maxsize
        min_trade_profit = int(self.min_trade_profit_input.text()) if self.min_trade_profit_input.text() else 0
        return max_scu, max_investment, max_outdated_in_days, min_trade_profit

    def get_selected_ids(self):
        departure_system_id = self.departure_system_combo.currentData()
        departure_planet_id = self.departure_planet_combo.currentData()
        if self.departure_planet_combo.currentData() == "all_planets":
            departure_planet_id = None
        destination_system_id = self.destination_system_combo.currentData()
        destination_planet_id = self.destination_planet_combo.currentData()
        if self.destination_planet_combo.currentData() == "all_planets":
            destination_planet_id = None
        return departure_system_id, departure_planet_id, destination_system_id, destination_planet_id

    async def calculate_trade_routes_users(self,
                                           commodities_routes,
                                           max_scu,
                                           max_investment,
                                           min_trade_profit):
        await self.ensure_initialized()
        trade_routes = await self.process_trade_route_users(commodities_routes,
                                                            max_scu,
                                                            max_investment,
                                                            min_trade_profit)
        await self.display_trade_routes(trade_routes, self.columns, quick=False)
        # Allow UI to update during the search
        QApplication.processEvents()
        return trade_routes

    async def get_terminals_from_planets(self, filtering_planets, filter_public_hangars=False, filter_space_only=False):
        await self.ensure_initialized()
        terminals = []
        universe = len(filtering_planets)
        self.progress_bar.setMaximum(universe)
        actionProgress = 0
        # Get all terminals (filter by system/planet) from /terminals
        for planet in filtering_planets:
            returned_terminals = await self.api.fetch_terminals(planet["id_star_system"],
                                                                planet["id"])
            for terminal in returned_terminals:
                if ((not filter_public_hangars
                     or (terminal["city_name"]
                         or terminal["space_station_name"]))
                    and (not filter_space_only
                         or terminal["space_station_name"])):
                    terminals.append(terminal)
            actionProgress += 1
            self.progress_bar.setValue(actionProgress)
        return terminals

    async def get_buy_commodities_from_terminals(self, departure_terminals):
        await self.ensure_initialized()
        buy_commodities = []
        universe = len(departure_terminals)
        self.progress_bar.setMaximum(universe)
        actionProgress = 0
        # Get all BUY commodities (for each departure terminals) from /commodities_prices
        for departure_terminal in departure_terminals:
            buy_commodities.extend([commodity for commodity in
                                    await self.api.fetch_commodities_from_terminal(departure_terminal["id"])
                                    if commodity.get("price_buy") > 0])
            actionProgress += 1
            self.progress_bar.setValue(actionProgress)
        self.logger.log(logging.INFO, f"{len(buy_commodities)} Buy Commodities found.")
        return buy_commodities

    async def get_sell_commodities_from_commodities_prices(self,
                                                           buy_commodities,
                                                           filter_public_hangars=False,
                                                           filter_space_only=False):
        await self.ensure_initialized()
        grouped_buy_commodities_ids = []
        # Establish a GROUPED list of BUY commodities (by commodity_id)
        grouped_buy_commodities_ids = set(map(lambda x: x["id_commodity"], buy_commodities))
        self.logger.log(logging.INFO, f"{len(grouped_buy_commodities_ids)} Unique Buy Commodities found.")

        sell_commodities = []
        universe = len(grouped_buy_commodities_ids)
        self.progress_bar.setMaximum(universe)
        actionProgress = 0
        # Get all SELL commodities (for each unique BUY commodity) from /commodities_prices
        for grouped_buy_id in grouped_buy_commodities_ids:
            sell_commodities.extend([commodity for commodity in await self.api.fetch_commodities_by_id(grouped_buy_id)
                                    if commodity["price_sell"] > 0
                                    and (not filter_public_hangars or
                                         (commodity["city_name"] or
                                          commodity["space_station_name"]))
                                    and (not filter_space_only or
                                         commodity["space_station_name"])])
            actionProgress += 1
            self.progress_bar.setValue(actionProgress)
        self.logger.log(logging.INFO, f"{len(sell_commodities)} Sell Commodities found.")
        return sell_commodities

    async def calculate_trade_routes_rework(self, buy_commodities, sell_commodities,
                                            max_scu, max_investment, ignore_stocks,
                                            ignore_demand, max_outdated_in_days,
                                            min_trade_profit):
        await self.ensure_initialized()
        # [Calculate trade routes]
        trade_routes = []
        universe = len(buy_commodities) * len(sell_commodities)
        self.progress_bar.setMaximum(universe)
        actionProgress = 0

        # For each BUY commodity / For each SELL commodity > Populate Trade routes (Display as it is populated)
        for buy_commodity in buy_commodities:
            for sell_commodity in sell_commodities:
                self.progress_bar.setValue(actionProgress)
                actionProgress += 1
                if buy_commodity["id_commodity"] != sell_commodity["id_commodity"]:
                    continue
                if buy_commodity["id_terminal"] == sell_commodity["id_terminal"]:
                    continue
                route = await self.process_single_trade_route(buy_commodity, sell_commodity, max_scu,
                                                              max_investment, max_outdated_in_days,
                                                              min_trade_profit,
                                                              ignore_stocks, ignore_demand)
                if route:
                    trade_routes.append(route)
                    await self.display_trade_routes(trade_routes, self.columns)
                    QApplication.processEvents()
        self.progress_bar.setValue(actionProgress)
        await self.display_trade_routes(trade_routes, self.columns, quick=False)
        QApplication.processEvents()
        return trade_routes

    async def check_validity_users(self, commodity_route):
        if self.filter_public_hangars_checkbox.isChecked():
            if not commodity_route.get("is_space_station_origin", 0)\
               and not commodity_route.get("is_space_station_destination", 0):
                return False
            terminal_origin = await self.api.fetch_terminals(commodity_route.get("id_star_system_origin"),
                                                             commodity_route.get("id_planet_origin"),
                                                             commodity_route.get("id_terminal_origin"))
            if (not terminal_origin[0].get("city_name")):
                return False
            terminal_destination = await self.api.fetch_terminals(commodity_route.get("id_star_system_destination"),
                                                                  commodity_route.get("id_planet_destination"),
                                                                  commodity_route.get("id_terminal_destination"))
            if not terminal_destination[0].get("city_name"):
                return False
        if self.filter_space_only_checkbox.isChecked():
            if not commodity_route.get("is_space_station_origin", 0)\
               or not commodity_route.get("is_space_station_destination", 0):
                return False
        return True

    async def process_trade_route_users(self,
                                        commodities_routes,
                                        max_scu,
                                        max_investment,
                                        min_trade_profit):
        await self.ensure_initialized()
        sorted_routes = []
        universe = len(commodities_routes)
        self.progress_bar.setMaximum(universe)
        actionProgress = 0
        for commodity_route in commodities_routes:
            actionProgress += 1
            self.progress_bar.setValue(actionProgress)
            if not (await self.check_validity_users(commodity_route)):
                continue

            available_scu = max_scu if self.ignore_stocks_checkbox.isChecked() else commodity_route.get("scu_origin", 0)
            demand_scu = max_scu if self.ignore_demand_checkbox.isChecked() else commodity_route.get("scu_destination", 0)

            price_buy = commodity_route.get("price_origin")
            price_sell = commodity_route.get("price_destination")

            if not price_buy or not price_sell or available_scu <= 0 or not demand_scu:
                continue

            max_buyable_scu = min(max_scu, available_scu, int(max_investment // price_buy), demand_scu)
            if max_buyable_scu <= 0:
                continue

            investment = price_buy * max_buyable_scu
            unit_margin = (price_sell - price_buy)
            total_margin = unit_margin * max_buyable_scu
            if (total_margin <= 0) or (total_margin < min_trade_profit):
                continue
            profit_margin = unit_margin / price_buy
            distance = await self.api.fetch_distance(commodity_route["id_terminal_origin"],
                                                     commodity_route["id_terminal_destination"],
                                                     commodity_route["id_commodity"])
            total_margin_by_distance = total_margin / distance
            unit_margin_by_distance = unit_margin / distance

            sorted_routes.append({
                "departure": commodity_route["origin_terminal_name"],
                "destination": commodity_route["destination_terminal_name"],
                "commodity": commodity_route["commodity_name"],
                "buy_scu": str(max_buyable_scu) + " "
                + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),
                "buy_price": str(price_buy) + " "
                + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
                "sell_price": str(price_sell) + " "
                + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
                "investment": str(investment) + " "
                + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
                "unit_margin": str(unit_margin) + " "
                + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
                "total_margin": str(total_margin) + " "
                + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
                "departure_scu_available": str(commodity_route.get('scu_origin', 0)) + " "
                + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),
                "arrival_demand_scu": str(commodity_route.get('scu_destination', 0)) + " "
                + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),
                "profit_margin": f"{round(profit_margin * 100)}%",
                "departure_terminal_id": commodity_route["id_terminal_origin"],
                "arrival_terminal_id": commodity_route["id_terminal_destination"],
                "departure_system_id": commodity_route["id_star_system_origin"],
                "arrival_system_id": commodity_route["id_star_system_destination"],
                "departure_planet_id": commodity_route["id_planet_origin"],
                "arrival_planet_id": commodity_route["id_planet_destination"],
                "commodity_id": commodity_route["id_commodity"],
                "max_buyable_scu": max_buyable_scu,
                "distance": distance,
                "total_margin_by_distance": str(total_margin_by_distance),
                "unit_margin_by_distance": str(unit_margin_by_distance)
            })
        return sorted_routes

    async def check_validity(self, buy_commodity, sell_commodity, max_scu, max_investment, max_outdated_in_days):
        if buy_commodity["id_commodity"] != sell_commodity["id_commodity"]:
            return False
        if buy_commodity["id_terminal"] == sell_commodity["id_terminal"]:
            return False
        if buy_commodity["id"] == sell_commodity["id"]:
            return False
        buy_update = buy_commodity["date_modified"]
        sell_update = sell_commodity["date_modified"]
        buy_update_days = days_difference_from_now(buy_update)
        sell_update_days = days_difference_from_now(sell_update)
        if (buy_update_days > max_outdated_in_days) or (sell_update_days > max_outdated_in_days):
            return False
        if max_scu < 0:
            # TODO - Send Exception instead
            return False
        if max_investment < 0:
            # TODO - Send Exception instead
            return False
        if max_outdated_in_days < 0:
            # TODO - Send Exception instead
            return False
        return True

    async def process_single_trade_route(self, buy_commodity, sell_commodity, max_scu=sys.maxsize,
                                         max_investment=sys.maxsize, max_outdated_in_days=sys.maxsize,
                                         min_trade_profit=0,
                                         ignore_stocks=False, ignore_demand=False):
        await self.ensure_initialized()
        route = None
        if not (await self.check_validity(buy_commodity,
                                          sell_commodity,
                                          max_scu,
                                          max_investment,
                                          max_outdated_in_days)):
            return None
        buy_update = buy_commodity["date_modified"]
        sell_update = sell_commodity["date_modified"]

        available_scu = max_scu if ignore_stocks else buy_commodity.get("scu_buy", 0)
        scu_sell_stock = sell_commodity.get("scu_sell_stock", 0)
        scu_sell_users = sell_commodity.get("scu_sell_users", 0)
        demand_scu = max_scu if ignore_demand else scu_sell_stock - scu_sell_users

        price_buy = buy_commodity.get("price_buy")
        price_sell = sell_commodity.get("price_sell")

        if not price_buy or not price_sell or available_scu <= 0 or not demand_scu:
            return route

        max_buyable_scu = min(max_scu, available_scu, int(max_investment // price_buy), demand_scu)
        if max_buyable_scu <= 0:
            return route

        investment = price_buy * max_buyable_scu
        unit_margin = (price_sell - price_buy)
        total_margin = unit_margin * max_buyable_scu
        if (total_margin <= 0) or (total_margin < min_trade_profit):
            return route
        profit_margin = unit_margin / price_buy
        distance = await self.api.fetch_distance(buy_commodity["id_terminal"],
                                                 sell_commodity["id_terminal"],
                                                 buy_commodity.get("id_commodity"))
        total_margin_by_distance = total_margin / distance
        unit_margin_by_distance = unit_margin / distance

        route = {
            "departure": buy_commodity["terminal_name"],
            "destination": sell_commodity["terminal_name"],
            "commodity": buy_commodity.get("commodity_name"),
            "buy_scu": str(max_buyable_scu) + " "
            + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),
            "buy_price": str(price_buy) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "sell_price": str(price_sell) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "investment": str(investment) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "unit_margin": str(unit_margin) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "total_margin": str(total_margin) + " "
            + self.translation_manager.get_translation("uec", self.config_manager.get_lang()),
            "departure_scu_available": str(buy_commodity.get('scu_buy', 0)) + " "
            + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),
            "arrival_demand_scu": str(scu_sell_stock - scu_sell_users) + " "
            + self.translation_manager.get_translation("scu", self.config_manager.get_lang()),
            "profit_margin": f"{round(profit_margin * 100)} %",
            "departure_terminal_id": buy_commodity["id_terminal"],
            "arrival_terminal_id": sell_commodity.get("id_terminal"),
            "departure_system_id": buy_commodity.get("id_star_system"),
            "arrival_system_id": sell_commodity.get("id_star_system"),
            "departure_planet_id": buy_commodity.get("id_planet"),
            "arrival_planet_id": sell_commodity.get("id_planet"),
            "commodity_id": buy_commodity.get("id_commodity"),
            "max_buyable_scu": max_buyable_scu,
            "buy_latest_update": str(buy_commodity["date_modified"]),
            "sell_latest_update": str(sell_commodity["date_modified"]),
            "oldest_update": str(buy_update) if buy_update < sell_update else str(sell_update),
            "latest_update": str(buy_update) if buy_update > sell_update else str(sell_update),
            "distance": distance,
            "total_margin_by_distance": str(total_margin_by_distance),
            "unit_margin_by_distance": str(unit_margin_by_distance)
        }
        return route

    async def display_trade_routes(self, trade_routes, columns, quick=True):
        await self.ensure_initialized()
        sorting_formula = self.sorting_options_combo.currentData()
        reverse_order = True if self.sorting_order_combo.currentData() == "DESC" else False
        nb_items = 5 if quick else self.page_items_combo.currentData()
        self.trade_route_table.setRowCount(0)  # Clear the table before adding sorted results
        trade_routes.sort(key=lambda x: float(x[sorting_formula].split()[0]), reverse=reverse_order)
        for i, route in enumerate(trade_routes[:nb_items]):
            self.trade_route_table.insertRow(i)
            for j, value in enumerate(route.values()):
                if j < len(columns) - 1:
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the item non-editable
                    self.trade_route_table.setItem(i, j, item)
                else:
                    await self.add_action_buttons(i, j, trade_routes[i])

        # Resize columns to fit contents
        self.trade_route_table.resizeColumnsToContents()

    async def add_action_buttons(self, i, j, trade_route):
        await self.ensure_initialized()
        action_layout = QHBoxLayout()
        buy_button = QPushButton(self.translation_manager.get_translation("select_to_buy",
                                                                          self.config_manager.get_lang()))
        buy_button.clicked.connect(create_async_callback(self.select_to_buy, trade_route))
        sell_button = QPushButton(self.translation_manager.get_translation("select_to_sell",
                                                                           self.config_manager.get_lang()))
        sell_button.clicked.connect(create_async_callback(self.select_to_sell, trade_route))
        action_layout.addWidget(buy_button)
        action_layout.addWidget(sell_button)
        action_widget = QWidget()
        action_widget.setLayout(action_layout)
        self.trade_route_table.setCellWidget(i, j, action_widget)

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
