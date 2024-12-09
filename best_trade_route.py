import logging
import sys
import re
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
from tools import create_async_callback, days_difference_from_now, translate


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
                    await translate("trade_columns_departure"),
                    await translate("trade_columns_destination"),
                    await translate("trade_columns_commodity"),
                    await translate("trade_columns_buy_scu"),
                    await translate("trade_columns_buy_price"),
                    await translate("trade_columns_sell_price"),
                    await translate("trade_columns_investment"),
                    await translate("trade_columns_unit_margin"),
                    await translate("trade_columns_total_margin"),
                    await translate("trade_columns_departure_scu_available"),
                    await translate("trade_columns_arrival_demand_scu"),
                    await translate("trade_columns_profit_margin"),
                    #await translate("trade_columns_arrival_terminal_mcs"),
                    await translate("trade_columns_actions")
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
        self.max_scu_input.setPlaceholderText(await translate("enter") + " " + await translate("maximum")
                                              + " " + await translate("scu"))
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("scu") + ":"))
        layout.addWidget(self.max_scu_input)
        self.max_investment_input = QLineEdit()
        self.max_investment_input.setPlaceholderText(await translate("enter")
                                                     + " "
                                                     + await translate("maximum") + " " + await translate("investment")
                                                     + " (" + await translate("uec") + ")")
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("investment")
                                + " (" + await translate("uec") + "):"))
        layout.addWidget(self.max_investment_input)
        self.max_outdated_input = QLineEdit()
        self.max_outdated_input.setPlaceholderText(
            await translate("enter") + " " + await translate("maximum") + " " + await translate("outdated")
            + " (" + await translate("days") + ") - "
            + await translate("not_user_trades"))
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("outdated")
                                + " (" + await translate("days") + "):"))
        layout.addWidget(self.max_outdated_input)
        self.min_trade_profit_input = QLineEdit()
        self.min_trade_profit_input.setPlaceholderText(
            await translate("enter") + " " + await translate("minimum") + " " + await translate("trade_columns_total_margin")
            + " (" + await translate("uec") + ")")
        self.min_trade_profit_input.setText("8000")
        layout.addWidget(QLabel(await translate("minimum") + " " + await translate("trade_columns_total_margin")
                                + " (" + await translate("uec") + "):"))
        layout.addWidget(self.min_trade_profit_input)
        self.departure_system_combo = QComboBox()
        self.departure_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_departure_planets())
        )
        layout.addWidget(QLabel(await translate("departure_system") + ":"))
        layout.addWidget(self.departure_system_combo)
        self.departure_planet_combo = QComboBox()
        self.departure_planet_combo.addItem(await translate("all_planets"), "all_planets")
        layout.addWidget(QLabel(await translate("departure_planet") + ":"))
        layout.addWidget(self.departure_planet_combo)
        self.destination_system_combo = QComboBox()
        self.destination_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_destination_planets())
        )
        self.destination_system_combo.addItem(await translate("all_systems"), "all_systems")
        layout.addWidget(QLabel(await translate("destination_system") + ":"))
        layout.addWidget(self.destination_system_combo)
        self.destination_planet_combo = QComboBox()
        self.destination_planet_combo.addItem(await translate("all_planets"), "all_planets")
        layout.addWidget(QLabel(await translate("destination_planet") + ":"))
        layout.addWidget(self.destination_planet_combo)
        self.ignore_stocks_checkbox = QCheckBox(await translate("ignore_stocks"))
        self.ignore_demand_checkbox = QCheckBox(await translate("ignore_demand"))
        layout.addWidget(self.ignore_stocks_checkbox)
        layout.addWidget(self.ignore_demand_checkbox)
        self.filter_public_hangars_checkbox = QCheckBox(await translate("no_public_hangars"))
        layout.addWidget(self.filter_public_hangars_checkbox)
        self.filter_space_only_checkbox = QCheckBox(await translate("space_only"))
        layout.addWidget(self.filter_space_only_checkbox)

        self.find_route_button_rework = QPushButton(await translate("find_best_trade_routes"))
        self.find_route_button_rework.clicked.connect(lambda: asyncio.ensure_future(self.find_best_trade_routes_rework()))
        layout.addWidget(self.find_route_button_rework)

        self.find_route_button_users = QPushButton(await translate("find_best_trade_from_user"))
        self.find_route_button_users.clicked.connect(lambda: asyncio.ensure_future(self.find_best_trade_routes_users()))
        layout.addWidget(self.find_route_button_users)

        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.main_progress_bar)
        layout.addWidget(self.progress_bar)

        self.page_items_combo = QComboBox()
        self.page_items_combo.addItem("10 " + await translate("maximum_results"), 10)
        self.page_items_combo.addItem("20 " + await translate("maximum_results"), 20)
        self.page_items_combo.addItem("50 " + await translate("maximum_results"), 50)
        self.page_items_combo.addItem("100 " + await translate("maximum_results"), 100)
        self.page_items_combo.addItem("500 " + await translate("maximum_results"), 500)
        self.page_items_combo.addItem("1000 " + await translate("maximum_results"), 1000)
        self.page_items_combo.setCurrentIndex(0)
        self.page_items_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_page_items())
        )
        layout.addWidget(self.page_items_combo)

        self.sorting_options_combo = QComboBox()
        self.sorting_options_combo.addItem(await translate("sort_trade_margin")
                                           + " (" + await translate("uec") + ")", "total_margin")
        self.sorting_options_combo.addItem(await translate("sort_profit_margin")
                                           + " (%)", "profit_margin")
        self.sorting_options_combo.addItem(await translate("sort_scu_margin")
                                           + " (" + await translate("uec") + "/" + await translate("scu") + ")",
                                           "unit_margin")
        self.sorting_options_combo.addItem(await translate("trade_columns_investment")
                                           + " (" + await translate("uec") + ")", "investment")
        self.sorting_options_combo.addItem(await translate("trade_columns_buy_scu")
                                           + " (" + await translate("unit_qty") + ")", "buy_scu")
        self.sorting_options_combo.addItem(await translate("total_margin_by_distance")
                                           + " (" + await translate("uec") + "/" + await translate("km") + ")",
                                           "total_margin_by_distance")
        self.sorting_options_combo.addItem(await translate("unit_margin_by_distance")
                                           + " (" + await translate("uec") + "/" + await translate("scu")
                                           + "/" + await translate("km") + ")",
                                           "unit_margin_by_distance")
        self.sorting_options_combo.setCurrentIndex(0)
        self.sorting_options_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_page_items())
        )
        layout.addWidget(self.sorting_options_combo)

        self.sorting_order_combo = QComboBox()
        self.sorting_order_combo.addItem(await translate("sort_descending"), "DESC")
        self.sorting_order_combo.addItem(await translate("sort_ascending"), "ASC")
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
                    self.departure_system_combo.blockSignals(True)
                    self.departure_system_combo.addItem(system["name"], system["id"])
                    self.destination_system_combo.blockSignals(True)
                    self.destination_system_combo.addItem(system["name"], system["id"])
                    if system.get("is_default") == 1:
                        self.departure_system_combo.blockSignals(False)
                        self.departure_system_combo.setCurrentIndex(self.departure_system_combo.count() - 1)
            logging.info("Systems loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load systems: {e}")
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_failed_to_load_systems") + f": {e}")
        finally:
            self.departure_system_combo.blockSignals(False)
            self.destination_system_combo.blockSignals(False)

    async def update_departure_planets(self):
        await self.ensure_initialized()
        self.departure_planet_combo.clear()
        self.departure_planet_combo.addItem(await translate("all_planets"), "all_planets")
        self.terminals = []
        system_id = self.departure_system_combo.currentData()
        if not system_id:
            return
        try:
            planets = await self.api.fetch_planets(system_id)
            for planet in planets:
                self.departure_planet_combo.addItem(planet["name"], planet["id"])
            self.departure_planet_combo.addItem(await translate("unknown_planet"), "unknown_planet")
            logging.info(f"Departure planets loaded successfully for star_system ID : {system_id}")
        except Exception as e:
            logging.error(f"Failed to load departure planets: {e}")
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_failed_to_load_departure_planets") + f": {e}")

    async def update_destination_planets(self):
        await self.ensure_initialized()
        self.destination_planet_combo.clear()
        self.destination_planet_combo.addItem(await translate("all_planets"), "all_planets")
        system_id = self.destination_system_combo.currentData()
        if not system_id and system_id != "all_systems":
            return
        try:
            planets = []
            if system_id != "all_systems":
                planets = await self.api.fetch_planets(system_id)
            else:
                planets = await self.api.fetch_planets()
            for planet in planets:
                self.destination_planet_combo.addItem(planet["name"], planet["id"])
            self.destination_planet_combo.addItem(await translate("unknown_planet"), "unknown_planet")
            logging.info(f"Destination planets loaded successfully for star_system ID : {system_id}")
        except Exception as e:
            logging.error(f"Failed to load destination planets: {e}")
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_failed_to_load_destination_planets") + f": {e}")

    async def update_page_items(self):
        await self.ensure_initialized()
        await self.display_trade_routes(self.current_trades, self.columns, quick=False)

    async def get_planets_from_systems(self, systems, planet_id, show_progress=False):
        planets = []
        universe = len(systems)
        if show_progress:
            self.progress_bar.setMaximum(universe)
        actionProgress = 0
        for system in systems:
            if planet_id == "all_planets":
                planets.extend(await self.api.fetch_planets(system["id"]))
            elif planet_id != "unknown_planet":
                planets.extend(await self.api.fetch_planets(system["id"], planet_id))
            actionProgress += 1
            if show_progress:
                self.progress_bar.setValue(actionProgress)
        return planets

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
            max_scu, max_investment, max_outdated_in_days, min_trade_profit = await self.get_input_values()
            departure_system_id, departure_planet_id, destination_system_id, destination_planet_id = \
                await self.get_selected_ids()

            if departure_planet_id == "unknown_planet" or destination_planet_id == "unknown_planet":
                raise Exception("User Trades is not compatible with Unknown Planet search")

            departure_planets = []
            if departure_planet_id == "all_planets":
                departure_planets = await self.api.fetch_planets(departure_system_id)
            elif departure_planet_id != "unknown_planet":
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

            destination_planets = await self.get_planets_from_systems(destination_systems,
                                                                      destination_planet_id,
                                                                      show_progress=True)
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
        except ValueError as e:
            self.logger.warning(f"Input Error: {e}")
            QMessageBox.warning(self, await translate("error_input_error"), str(e))
        except Exception as e:
            self.logger.log(logging.ERROR, f"An error occurred while finding best trade routes: {e}")
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_generic") + f": {e}")
        finally:
            await self.main_widget.set_gui_enabled(True)
            self.main_progress_bar.setVisible(False)
            self.progress_bar.setVisible(False)

    async def get_planets_from_single_ids(self, system_id, planet_id):
        planets = []
        if planet_id == "all_planets":
            planets = await self.api.fetch_planets(system_id)
        elif planet_id != "unknown_planet":
            planets = await self.api.fetch_planets(system_id, planet_id)
        return planets

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
            max_scu, max_investment, max_outdated_in_days, min_trade_profit = \
                await self.get_input_values()
            departure_system_id, departure_planet_id, destination_system_id, destination_planet_id = \
                await self.get_selected_ids()
            ignore_stocks = self.ignore_stocks_checkbox.isChecked()
            ignore_demand = self.ignore_demand_checkbox.isChecked()
            filter_public_hangars = self.filter_public_hangars_checkbox.isChecked()
            filter_space_only = self.filter_space_only_checkbox.isChecked()

            # [Recover departure/destination planets]
            departure_planets = await self.get_planets_from_single_ids(departure_system_id, departure_planet_id)
            self.logger.log(logging.INFO, f"{len(departure_planets)} Departure Planets found.")
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
            universe = len(destination_systems) if destination_planet_id != "unknown_planet" else 1
            self.progress_bar.setMaximum(universe)
            actionProgress = 0
            if destination_planet_id == "all_planets":
                for destination_system in destination_systems:
                    destination_planets.extend(await self.api.fetch_planets(destination_system["id"]))
                    actionProgress += 1
                    self.progress_bar.setValue(actionProgress)
                self.logger.log(logging.INFO, f"{len(destination_planets)} Destination Planets found.")
            elif destination_planet_id == "unknown_planet":
                actionProgress += 1
                self.progress_bar.setValue(actionProgress)
                self.logger.log(logging.INFO, "Unknown Destination Planets.")
            else:
                destination_planets = await self.api.fetch_planets(destination_system_id, destination_planet_id)
                actionProgress += 1
                self.progress_bar.setValue(actionProgress)
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            # [Recover departure/destination terminals and commodities]
            departure_terminals = await self.get_terminals_from_planets(departure_planets,
                                                                        filter_public_hangars,
                                                                        filter_space_only,
                                                                        departure_system_id)
            self.logger.log(logging.INFO, f"{len(departure_terminals)} Departure Terminals found.")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            buy_commodities = await self.get_buy_commodities_from_terminals(departure_terminals)
            self.logger.log(logging.INFO, f"{len(buy_commodities)} Buy Commodities found.")
            currentProgress += 1
            self.main_progress_bar.setValue(currentProgress)

            sell_commodities = await self.get_sell_commodities_from_commodities_prices(buy_commodities,
                                                                                       destination_planets,
                                                                                       filter_public_hangars,
                                                                                       filter_space_only,
                                                                                       destination_systems)
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
        except ValueError as e:
            self.logger.warning(f"Input Error: {e}")
            QMessageBox.warning(self, await translate("error_input_error"), str(e))
        except Exception as e:
            import traceback
            if self.config_manager.get_debug():
                traceback.print_exc()
            else:
                self.logger.log(logging.ERROR, f"An error occurred while finding best trade routes: {e}")
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_generic") + f": {e}")
        finally:
            await self.main_widget.set_gui_enabled(True)
            self.progress_bar.setVisible(False)
            self.main_progress_bar.setVisible(False)

    async def get_input_values(self):
        if not re.match(r'^\d+$', self.max_scu_input.text()) and self.max_scu_input.text() != "":
            raise ValueError(await translate("scu") + " " + await translate("error_input_invalid_integer"))
        if not re.match(r'^\d+(\.\d+)?$', self.max_investment_input.text()) and self.max_investment_input.text() != "":
            raise ValueError(await translate("max_investment") + " " + await translate("error_input_invalid_number"))
        if not re.match(r'^\d+$', self.max_outdated_input.text()) and self.max_outdated_input.text() != "":
            raise ValueError(await translate("days") + " " + await translate("error_input_invalid_integer"))
        if not re.match(r'^\d+$', self.min_trade_profit_input.text()) and self.min_trade_profit_input.text() != "":
            raise ValueError(await translate("trade_columns_profit_margin")
                             + " " + await translate("error_input_invalid_integer"))
        max_scu = int(self.max_scu_input.text()) if self.max_scu_input.text() else sys.maxsize
        max_investment = float(self.max_investment_input.text()) if self.max_investment_input.text() else sys.maxsize
        max_outdated_in_days = int(self.max_outdated_input.text()) if self.max_outdated_input.text() else sys.maxsize
        min_trade_profit = int(self.min_trade_profit_input.text()) if self.min_trade_profit_input.text() else 0
        return max_scu, max_investment, max_outdated_in_days, min_trade_profit

    async def get_selected_ids(self):
        departure_system_id = self.departure_system_combo.currentData()
        departure_planet_id = self.departure_planet_combo.currentData()
        destination_system_id = self.destination_system_combo.currentData()
        if self.destination_system_combo.currentData() == "all_systems":
            destination_system_id = None
        destination_planet_id = self.destination_planet_combo.currentData()
        if not departure_system_id:
            raise ValueError(await translate("error_input_select_ds"))
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

    async def get_terminals_from_planets(self, filtering_planets,
                                         filter_public_hangars=False,
                                         filter_space_only=False,
                                         filtering_system_id=None):
        await self.ensure_initialized()
        terminals = []
        universe = len(filtering_planets)
        # Get all terminals (filter by system/planet) from /terminals
        if universe == 0 and filtering_system_id:
            self.progress_bar.setMaximum(1)
            actionProgress = 0
            returned_terminals = [terminal for terminal in await self.api.fetch_terminals(filtering_system_id)
                                  if terminal.get("id_planet") == 0]
            for terminal in returned_terminals:
                if ((not filter_public_hangars
                    or (terminal["city_name"]
                        or terminal["space_station_name"]))
                    and (not filter_space_only
                         or terminal["space_station_name"])):
                    terminals.append(terminal)
            actionProgress += 1
            self.progress_bar.setValue(actionProgress)
        else:
            self.progress_bar.setMaximum(universe)
            actionProgress = 0
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
                                                           destination_planets,
                                                           filter_public_hangars=False,
                                                           filter_space_only=False,
                                                           destination_systems=[]):
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
            unfiltered_commodities = await self.api.fetch_commodities_by_id(grouped_buy_id)
            for unfiltered_commodity in unfiltered_commodities:
                if (unfiltered_commodity["price_sell"] > 0
                    and (not filter_public_hangars
                         or (unfiltered_commodity["city_name"]
                             or unfiltered_commodity["space_station_name"]))
                    and (not filter_space_only
                         or unfiltered_commodity["space_station_name"])):
                    if len(destination_planets) == 0:
                        for destination_system in destination_systems:
                            if (unfiltered_commodity["id_star_system"] == destination_system.get("id")
                               and unfiltered_commodity["id_planet"] == 0):
                                sell_commodities.append(unfiltered_commodity)
                    else:
                        for destination_planet in destination_planets:
                            if (unfiltered_commodity["id_star_system"] == destination_planet["id_star_system"]
                                and ((not unfiltered_commodity["id_planet"] and len(destination_planets) > 1)
                                     or (unfiltered_commodity["id_planet"] == destination_planet["id"]))):
                                sell_commodities.append(unfiltered_commodity)
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

            arrival_terminal = await self.api.fetch_terminals(commodity_route["id_star_system_destination"],
                                                              commodity_route["id_planet_destination"],
                                                              commodity_route["id_terminal_destination"])
            arrival_terminal_mcs = arrival_terminal[0].get("mcs")
            distance = await self.api.fetch_distance(commodity_route["id_terminal_origin"],
                                                     commodity_route["id_terminal_destination"],
                                                     commodity_route["id_commodity"])
            total_margin_by_distance = total_margin / distance
            unit_margin_by_distance = unit_margin / distance

            sorted_routes.append({
                "departure": commodity_route["origin_terminal_name"],
                "destination": commodity_route["destination_terminal_name"],
                "commodity": commodity_route["commodity_name"],
                "buy_scu": str(max_buyable_scu) + " " + await translate("scu"),
                "buy_price": str(price_buy) + " " + await translate("scu"),
                "sell_price": str(price_sell) + " " + await translate("uec"),
                "investment": str(investment) + " " + await translate("uec"),
                "unit_margin": str(unit_margin) + " " + await translate("uec"),
                "total_margin": str(total_margin) + " " + await translate("uec"),
                "departure_scu_available": str(commodity_route.get('scu_origin', 0)) + " " + await translate("scu"),
                "arrival_demand_scu": str(commodity_route.get('scu_destination', 0)) + " " + await translate("scu"),
                "profit_margin": f"{round(profit_margin * 100)}%",
                "arrival_terminal_mcs": arrival_terminal_mcs,
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

        arrival_terminal = await self.api.fetch_terminals(sell_commodity["id_star_system"],
                                                          sell_commodity["id_planet"],
                                                          sell_commodity["id_terminal"])
        arrival_terminal_mcs = arrival_terminal[0].get("mcs")

        route = {
            "departure": buy_commodity["terminal_name"],
            "destination": sell_commodity["terminal_name"],
            "commodity": buy_commodity.get("commodity_name"),
            "buy_scu": str(max_buyable_scu) + " " + await translate("scu"),
            "buy_price": str(price_buy) + " " + await translate("uec"),
            "sell_price": str(price_sell) + " " + await translate("uec"),
            "investment": str(investment) + " " + await translate("uec"),
            "unit_margin": str(unit_margin) + " " + await translate("uec"),
            "total_margin": str(total_margin) + " " + await translate("uec"),
            "departure_scu_available": str(buy_commodity.get('scu_buy', 0)) + " " + await translate("scu"),
            "arrival_demand_scu": str(scu_sell_stock - scu_sell_users) + " " + await translate("scu"),
            "profit_margin": f"{round(profit_margin * 100)} %",
            "arrival_terminal_mcs": arrival_terminal_mcs,
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
        buy_button = QPushButton(await translate("select_to_buy"))
        buy_button.clicked.connect(create_async_callback(self.select_to_buy, trade_route))
        sell_button = QPushButton(await translate("select_to_sell"))
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
            QMessageBox.critical(self, await translate("error_error"), await translate("error_generic"))

    async def select_to_sell(self, trade_route):
        await self.ensure_initialized()
        self.logger.log(logging.INFO, "Selected route to sell")
        trade_tab = self.main_widget.findChild(TradeTab)
        if trade_tab:
            self.main_widget.loop.create_task(trade_tab.select_trade_route(trade_route, is_buy=False))
        else:
            self.logger.log(logging.ERROR, "An error occurred while selecting trade route")
            QMessageBox.critical(self, await translate("error_error"), await translate("error_generic"))

    def set_gui_enabled(self, enabled):
        for input in self.findChildren(QLineEdit):
            input.setEnabled(enabled)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.setEnabled(enabled)
        for combo in self.findChildren(QComboBox):
            combo.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)
