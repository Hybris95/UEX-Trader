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
import traceback


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
                self.config_manager = await ConfigManager.get_instance()
                self.api = await API.get_instance(self.config_manager)
                self.translation_manager = await TranslationManager.get_instance()
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
                    await translate("trade_columns_mcs"),
                    await translate("trade_columns_actions")
                ]
                await self.init_ui()
                self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    async def prep_max_scu(self):
        self.max_scu_input = QLineEdit()
        self.max_scu_input.setPlaceholderText(await translate("enter") + " " + await translate("maximum")
                                              + " " + await translate("scu"))

    async def prep_max_investment(self):
        self.max_investment_input = QLineEdit()
        self.max_investment_input.setPlaceholderText(await translate("enter")
                                                     + " "
                                                     + await translate("maximum") + " " + await translate("investment")
                                                     + " (" + await translate("uec") + ")")

    async def prep_max_outdated(self):
        self.max_outdated_input = QLineEdit()
        self.max_outdated_input.setPlaceholderText(
            await translate("enter") + " " + await translate("maximum") + " " + await translate("outdated")
            + " (" + await translate("days") + ") - "
            + await translate("not_user_trades"))

    async def prep_min_trade_profit(self):
        self.min_trade_profit_input = QLineEdit()
        self.min_trade_profit_input.setPlaceholderText(
            await translate("enter") + " " + await translate("minimum") + " " + await translate("trade_columns_total_margin")
            + " (" + await translate("uec") + ")")
        self.min_trade_profit_input.setText("8000")

    async def prep_departure_system(self):
        self.departure_system_combo = QComboBox()
        self.departure_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_departure_planets())
        )

    async def prep_departure_planet(self):
        self.departure_planet_combo = QComboBox()
        self.departure_planet_combo.addItem(await translate("all_planets"), "all_planets")

    async def prep_destination_system(self):
        self.destination_system_combo = QComboBox()
        self.destination_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_destination_planets())
        )
        self.destination_system_combo.addItem(await translate("all_systems"), "all_systems")

    async def prep_destination_planet(self):
        self.destination_planet_combo = QComboBox()
        self.destination_planet_combo.addItem(await translate("all_planets"), "all_planets")

    async def prep_find_route_rework(self):
        self.find_route_button_rework = QPushButton(await translate("find_best_trade_routes"))
        self.find_route_button_rework.clicked.connect(lambda: asyncio.ensure_future(self.find_best_trade_routes_rework()))

    async def prep_find_route_users(self):
        self.find_route_button_users = QPushButton(await translate("find_best_trade_from_user"))
        self.find_route_button_users.clicked.connect(lambda: asyncio.ensure_future(self.find_best_trade_routes_users()))

    async def prep_main_progress(self):
        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setVisible(False)

    async def prep_progress(self):
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

    async def prep_page_items(self):
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

    async def prep_sorting_options(self):
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

    async def prep_sorting_order(self):
        self.sorting_order_combo = QComboBox()
        self.sorting_order_combo.addItem(await translate("sort_descending"), "DESC")
        self.sorting_order_combo.addItem(await translate("sort_ascending"), "ASC")
        self.sorting_order_combo.setCurrentIndex(0)
        self.sorting_order_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_page_items())
        )

    async def prep_ui(self):
        await self.prep_max_scu()
        await self.prep_max_investment()
        await self.prep_max_outdated()
        await self.prep_min_trade_profit()
        await self.prep_departure_system()
        await self.prep_departure_planet()
        await self.prep_destination_system()
        await self.prep_destination_planet()
        await self.prep_find_route_rework()
        await self.prep_find_route_users()
        await self.prep_main_progress()
        await self.prep_progress()
        await self.prep_page_items()
        await self.prep_sorting_options()
        await self.prep_sorting_order()

    async def add_widgets(self, layout):
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("scu") + ":"))
        layout.addWidget(self.max_scu_input)
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("investment")
                                + " (" + await translate("uec") + "):"))
        layout.addWidget(self.max_investment_input)
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("outdated")
                                + " (" + await translate("days") + "):"))
        layout.addWidget(self.max_outdated_input)
        layout.addWidget(QLabel(await translate("minimum") + " " + await translate("trade_columns_total_margin")
                                + " (" + await translate("uec") + "):"))
        layout.addWidget(self.min_trade_profit_input)
        layout.addWidget(QLabel(await translate("departure_system") + ":"))
        layout.addWidget(self.departure_system_combo)
        layout.addWidget(QLabel(await translate("departure_planet") + ":"))
        layout.addWidget(self.departure_planet_combo)
        layout.addWidget(QLabel(await translate("destination_system") + ":"))
        layout.addWidget(self.destination_system_combo)
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
        layout.addWidget(self.find_route_button_rework)
        layout.addWidget(self.find_route_button_users)
        layout.addWidget(self.main_progress_bar)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.page_items_combo)
        layout.addWidget(self.sorting_options_combo)
        layout.addWidget(self.sorting_order_combo)
        self.trade_route_table = QTableWidget()
        layout.addWidget(self.trade_route_table)

    async def init_ui(self):
        await self.prep_ui()
        layout = QVBoxLayout()
        await self.add_widgets(layout)
        self.setLayout(layout)

    async def load_systems(self):
        try:
            await self.ensure_initialized()
            for system in (await self.api.fetch_all_systems()):
                self.departure_system_combo.blockSignals(True)
                self.departure_system_combo.addItem(system["name"], system["id"])
                self.destination_system_combo.blockSignals(True)
                self.destination_system_combo.addItem(system["name"], system["id"])
                if system.get("is_default") == 1:
                    self.departure_system_combo.blockSignals(False)
                    self.departure_system_combo.setCurrentIndex(self.departure_system_combo.count() - 1)
            logging.info("Systems loaded successfully.")
        except Exception as e:
            logging.error("Failed to load systems: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
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
            logging.info("Departure planets loaded successfully for star_system ID : %s", system_id)
        except Exception as e:
            logging.error("Failed to load departure planets: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
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
            logging.info("Destination planets loaded successfully for star_system ID : %s", system_id)
        except Exception as e:
            logging.error("Failed to load destination planets: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
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
        action_progress = 0
        for system in systems:
            if planet_id == "all_planets":
                planets.extend(await self.api.fetch_planets(system["id"]))
            elif planet_id != "unknown_planet":
                planets.extend(await self.api.fetch_planets(system["id"], planet_id))
            action_progress += 1
            if show_progress:
                self.progress_bar.setValue(action_progress)
        return planets

    def check_unknown_planets(self, departure_planet_id, destination_planet_id):
        if departure_planet_id == "unknown_planet" or destination_planet_id == "unknown_planet":
            raise ValueError("User Trades is not compatible with Unknown Planet search")

    async def get_departure_planets(self, departure_planet_id, departure_system_id):
        if departure_planet_id == "all_planets":
            return await self.api.fetch_planets(departure_system_id)
        elif departure_planet_id != "unknown_planet":
            return await self.api.fetch_planets(departure_system_id, departure_planet_id)
        return []

    async def get_destination_systems(self, destination_system_id, departure_system_id):
        if not destination_system_id:
            return await self.api.fetch_systems_from_origin_system(departure_system_id, 2)
        else:
            return await self.api.fetch_system(destination_system_id)

    async def find_best_trade_routes_users(self):
        await self.ensure_initialized()
        self.logger.info("Searching for Best Trade Routes")
        self.trade_route_table.setRowCount(0)  # Clear previous results
        self.trade_route_table.setColumnCount(len(self.columns))
        self.trade_route_table.setHorizontalHeaderLabels(self.columns)
        await self.main_widget.set_gui_enabled(False)
        self.main_progress_bar.setVisible(True)
        self.progress_bar.setVisible(True)
        current_progress = 0
        self.progress_bar.setValue(current_progress)
        self.main_progress_bar.setValue(current_progress)
        self.main_progress_bar.setMaximum(5)

        try:
            inputs = await self.get_input_values()
            max_scu = inputs[0]
            max_investment = inputs[1]
            min_trade_profit = inputs[3]
            departure_system_id, departure_planet_id, destination_system_id, destination_planet_id = \
                await self.get_selected_ids()
            self.check_unknown_planets(departure_planet_id, destination_planet_id)

            departure_planets = await self.get_departure_planets(departure_planet_id, departure_system_id)
            self.logger.info("%s departure planets found", len(departure_planets))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            destination_systems = await self.get_destination_systems(destination_system_id, departure_system_id)
            self.logger.info("%s destination systems found", len(destination_systems))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            destination_planets = await self.get_planets_from_systems(destination_systems,
                                                                      destination_planet_id,
                                                                      show_progress=True)
            self.logger.info("%s destination planets found", len(destination_planets))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            commodities_routes = []
            universe = len(departure_planets) * len(destination_planets)
            self.progress_bar.setMaximum(universe)
            action_progress = 0
            if len(departure_planets) > 1:
                universe = universe + len(destination_planets)
                self.progress_bar.setMaximum(universe)
                for destination_planet in destination_planets:
                    commodities_routes.extend(await self.api.fetch_unknown_routes_from_system(departure_system_id,
                                                                                              destination_planet["id"]))
                    action_progress += 1
                    self.progress_bar.setValue(action_progress)
            for departure_planet in departure_planets:
                for destination_planet in destination_planets:
                    commodities_routes.extend(await self.api.fetch_routes(departure_planet["id"], destination_planet["id"]))
                    action_progress += 1
                    self.progress_bar.setValue(action_progress)
            self.logger.info("%s commodities routes to parse", len(commodities_routes))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            self.current_trades = await self.calculate_trade_routes_users(commodities_routes,
                                                                          max_scu,
                                                                          max_investment,
                                                                          min_trade_profit)
            self.logger.info("%s routes found", len(self.current_trades))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)
            self.logger.info("Finished calculating Best Trade Routes")
        except ValueError as e:
            self.logger.warning("Input Error: %s", e)
            QMessageBox.warning(self, await translate("error_input_error"), str(e))
        except Exception as e:
            self.logger.error("An error occurred while finding best trade routes: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
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
        current_progress = 0
        self.progress_bar.setValue(current_progress)
        self.main_progress_bar.setValue(current_progress)
        self.main_progress_bar.setMaximum(7)

        try:
            # [Recover entry parameters]
            departure_system_id, departure_planet_id, destination_system_id, destination_planet_id = \
                await self.get_selected_ids()
            ignore_stocks = self.ignore_stocks_checkbox.isChecked()
            ignore_demand = self.ignore_demand_checkbox.isChecked()
            filter_public_hangars = self.filter_public_hangars_checkbox.isChecked()
            filter_space_only = self.filter_space_only_checkbox.isChecked()

            # [Recover departure/destination planets]
            departure_planets = await self.get_planets_from_single_ids(departure_system_id, departure_planet_id)
            self.logger.info("%s Departure Planets found.", len(departure_planets))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            destination_systems = []
            if not destination_system_id:
                destination_systems = await self.api.fetch_systems_from_origin_system(departure_system_id, max_bounce=2)
                self.logger.info("%s Destination Systems found.", len(destination_systems))
            else:
                destination_systems = await self.api.fetch_system(destination_system_id)
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            destination_planets = []
            universe = len(destination_systems) if destination_planet_id != "unknown_planet" else 1
            self.progress_bar.setMaximum(universe)
            action_progress = 0
            if destination_planet_id == "all_planets":
                for destination_system in destination_systems:
                    destination_planets.extend(await self.api.fetch_planets(destination_system["id"]))
                    action_progress += 1
                    self.progress_bar.setValue(action_progress)
                self.logger.info("%s Destination Planets found.", len(destination_planets))
            elif destination_planet_id == "unknown_planet":
                action_progress += 1
                self.progress_bar.setValue(action_progress)
                self.logger.info("Unknown Destination Planets.")
            else:
                destination_planets = await self.api.fetch_planets(destination_system_id, destination_planet_id)
                action_progress += 1
                self.progress_bar.setValue(action_progress)
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            # [Recover departure/destination terminals and commodities]
            departure_terminals = await self.get_terminals_from_planets(departure_planets,
                                                                        filter_public_hangars,
                                                                        filter_space_only,
                                                                        departure_system_id)
            self.logger.info("%s Departure Terminals found.", len(departure_terminals))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            buy_commodities = await self.get_buy_commodities_from_terminals(departure_terminals)
            self.logger.info("%s Buy Commodities found.", len(buy_commodities))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            sell_commodities = await self.get_sell_commodities_from_commodities_prices(buy_commodities,
                                                                                       destination_planets,
                                                                                       filter_public_hangars,
                                                                                       filter_space_only,
                                                                                       destination_systems)
            self.logger.info("%s Sell Commodities found.", len(sell_commodities))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)

            self.current_trades = await self.calculate_trade_routes_rework(buy_commodities, sell_commodities,
                                                                           ignore_stocks, ignore_demand)
            self.logger.info("%s Trade routes found.", len(self.current_trades))
            current_progress += 1
            self.main_progress_bar.setValue(current_progress)
            self.logger.info("Finished calculating Best Trade Routes : %s found", len(self.current_trades))
        except ValueError as e:
            self.logger.warning("Input Error: %s", e)
            QMessageBox.warning(self, await translate("error_input_error"), str(e))
        except Exception as e:
            self.logger.error("An error occurred while finding best trade routes: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
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
        returned_terminals = []
        # Get all terminals (filter by system/planet) from /terminals
        if universe == 0 and filtering_system_id:
            self.progress_bar.setMaximum(1)
            action_progress = 0
            returned_terminals.extend([terminal for terminal in await self.api.fetch_terminals(filtering_system_id)
                                       if terminal.get("id_planet") == 0])
            action_progress += 1
            self.progress_bar.setValue(action_progress)
        else:
            self.progress_bar.setMaximum(universe)
            action_progress = 0
            if universe > 1 and filtering_system_id:
                returned_terminals.extend([terminal for terminal in await self.api.fetch_terminals(filtering_system_id)
                                           if terminal.get("id_planet") == 0])
            for planet in filtering_planets:
                returned_terminals.extend((await self.api.fetch_terminals(planet["id_star_system"],
                                                                          planet["id"])))
                action_progress += 1
                self.progress_bar.setValue(action_progress)
        for terminal in returned_terminals:
            if ((not filter_public_hangars
                or (terminal["city_name"]
                    or terminal["space_station_name"]))
                and (not filter_space_only
                     or terminal["space_station_name"])):
                terminals.append(terminal)
        return terminals

    async def get_buy_commodities_from_terminals(self, departure_terminals):
        await self.ensure_initialized()
        buy_commodities = []
        universe = len(departure_terminals)
        self.progress_bar.setMaximum(universe)
        action_progress = 0
        # Get all BUY commodities (for each departure terminals) from /commodities_prices
        for departure_terminal in departure_terminals:
            buy_commodities.extend([commodity for commodity in
                                    await self.api.fetch_commodities_from_terminal(departure_terminal["id"])
                                    if commodity.get("price_buy") > 0])
            action_progress += 1
            self.progress_bar.setValue(action_progress)
        self.logger.info("%s Buy Commodities found.", len(buy_commodities))
        return buy_commodities

    def append_unfiltered_commodity(self, unfiltered_commodity, sell_commodities,
                                    destination_planets, destination_systems):
        if len(destination_planets) == 0:
            for destination_system in destination_systems:
                if ((unfiltered_commodity["id_star_system"] == destination_system.get("id")
                     and unfiltered_commodity["id_planet"] == 0)):
                    sell_commodities.append(unfiltered_commodity)
        else:
            for destination_planet in destination_planets:
                if (unfiltered_commodity["id_star_system"] == destination_planet["id_star_system"]
                    and ((not unfiltered_commodity["id_planet"] and len(destination_planets) > 1)
                         or (unfiltered_commodity["id_planet"] == destination_planet["id"]))):
                    sell_commodities.append(unfiltered_commodity)

    async def get_sell_commodities_from_commodities_prices(self,
                                                           buy_commodities,
                                                           destination_planets,
                                                           filter_public_hangars=False,
                                                           filter_space_only=False,
                                                           destination_systems=None):
        await self.ensure_initialized()
        if not destination_systems:
            destination_systems = []
        grouped_buy_commodities_ids = []
        # Establish a GROUPED list of BUY commodities (by commodity_id)
        grouped_buy_commodities_ids = set(map(lambda x: x["id_commodity"], buy_commodities))
        self.logger.info("%s Unique Buy Commodities found.", len(grouped_buy_commodities_ids))

        sell_commodities = []
        universe = len(grouped_buy_commodities_ids)
        self.progress_bar.setMaximum(universe)
        action_progress = 0
        # Get all SELL commodities (for each unique BUY commodity) from /commodities_prices
        for grouped_buy_id in grouped_buy_commodities_ids:
            unfiltered_commodities = await self.api.fetch_commodities_by_id(grouped_buy_id)
            for unfiltered_commodity in unfiltered_commodities:
                filtered_public_hangars = (not filter_public_hangars
                                           or (unfiltered_commodity["city_name"]
                                               or unfiltered_commodity["space_station_name"]))
                filtered_space_only = (not filter_space_only
                                       or unfiltered_commodity["space_station_name"])
                if ((unfiltered_commodity["price_sell"] > 0
                     and filtered_public_hangars
                     and filtered_space_only)):
                    self.append_unfiltered_commodity(unfiltered_commodity, sell_commodities,
                                                     destination_planets, destination_systems)
            action_progress += 1
            self.progress_bar.setValue(action_progress)
        self.logger.info("%s Sell Commodities found.", len(sell_commodities))
        return sell_commodities

    async def calculate_trade_routes_rework(self, buy_commodities, sell_commodities, ignore_stocks, ignore_demand):
        await self.ensure_initialized()
        # [Calculate trade routes]
        trade_routes = []
        universe = len(buy_commodities) * len(sell_commodities)
        self.progress_bar.setMaximum(universe)
        action_progress = 0

        # For each BUY commodity / For each SELL commodity > Populate Trade routes (Display as it is populated)
        for buy_commodity in buy_commodities:
            for sell_commodity in sell_commodities:
                self.progress_bar.setValue(action_progress)
                action_progress += 1
                if buy_commodity["id_commodity"] != sell_commodity["id_commodity"]:
                    continue
                if buy_commodity["id_terminal"] == sell_commodity["id_terminal"]:
                    continue
                route = await self.process_single_trade_route(buy_commodity, sell_commodity, ignore_stocks, ignore_demand)
                if route:
                    trade_routes.append(route)
                    await self.display_trade_routes(trade_routes, self.columns)
                    QApplication.processEvents()
        self.progress_bar.setValue(action_progress)
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
        action_progress = 0
        for commodity_route in commodities_routes:
            action_progress += 1
            self.progress_bar.setValue(action_progress)
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

            terminal_origin = await self.api.fetch_terminals(commodity_route["id_star_system_origin"],
                                                             commodity_route["id_planet_origin"],
                                                             commodity_route["id_terminal_origin"])

            terminal_destination = await self.api.fetch_terminals(commodity_route["id_star_system_destination"],
                                                                  commodity_route["id_planet_destination"],
                                                                  commodity_route["id_terminal_destination"])

            mcs_origin = terminal_origin[0].get("max_container_size")
            mcs_destination = terminal_destination[0].get("max_container_size")
            mcs = min(mcs_origin, mcs_destination)

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
                "mcs": mcs,
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

    async def check_validity(self, buy_commodity, sell_commodity):
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

        inputs = await self.get_input_values()
        max_scu = inputs[0]
        max_investment = inputs[1]
        max_outdated_in_days = inputs[2]

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

    async def get_max_buyable_scu(self, ignore_stocks, ignore_demand,
                                  sell_commodity, buy_commodity):
        scu_sell_stock = sell_commodity.get("scu_sell_stock", 0)
        scu_sell_users = sell_commodity.get("scu_sell_users", 0)
        price_buy = buy_commodity.get("price_buy")
        price_sell = sell_commodity.get("price_sell")

        inputs = await self.get_input_values()
        max_scu = inputs[0]
        max_investment = inputs[1]

        available_scu = max_scu if ignore_stocks else buy_commodity.get("scu_buy", 0)
        demand_scu = max_scu if ignore_demand else scu_sell_stock - scu_sell_users

        if not price_buy or not price_sell or available_scu <= 0 or not demand_scu:
            return 0
        return min(max_scu, available_scu, int(max_investment // price_buy), demand_scu)

    async def process_single_trade_route(self, buy_commodity, sell_commodity,
                                         ignore_stocks=False, ignore_demand=False):
        await self.ensure_initialized()
        route = None
        if not (await self.check_validity(buy_commodity,
                                          sell_commodity)):
            return None

        scu_sell_stock = sell_commodity.get("scu_sell_stock", 0)
        scu_sell_users = sell_commodity.get("scu_sell_users", 0)
        price_buy = buy_commodity.get("price_buy")
        price_sell = sell_commodity.get("price_sell")

        max_buyable_scu = await self.get_max_buyable_scu(ignore_stocks, ignore_demand,
                                                         sell_commodity, buy_commodity)
        if max_buyable_scu <= 0:
            return route

        investment = price_buy * max_buyable_scu
        unit_margin = (price_sell - price_buy)
        total_margin = unit_margin * max_buyable_scu
        min_trade_profit = int(self.min_trade_profit_input.text()) if self.min_trade_profit_input.text() else 0
        if (total_margin <= 0) or (total_margin < min_trade_profit):
            return route
        profit_margin = unit_margin / price_buy
        distance = await self.api.fetch_distance(buy_commodity["id_terminal"],
                                                 sell_commodity["id_terminal"],
                                                 buy_commodity.get("id_commodity"))
        total_margin_by_distance = total_margin / distance
        unit_margin_by_distance = unit_margin / distance

        terminal_origin = await self.api.fetch_terminals(buy_commodity["id_star_system"],
                                                         buy_commodity["id_planet"],
                                                         buy_commodity["id_terminal"])

        terminal_destination = await self.api.fetch_terminals(sell_commodity["id_star_system"],
                                                              sell_commodity["id_planet"],
                                                              sell_commodity["id_terminal"])

        mcs_origin = terminal_origin[0].get("max_container_size")
        mcs_destination = terminal_destination[0].get("max_container_size")
        mcs = min(mcs_origin, mcs_destination)

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
            "mcs": mcs,
            "departure_terminal_id": buy_commodity["id_terminal"],
            "arrival_terminal_id": sell_commodity.get("id_terminal"),
            "departure_system_id": buy_commodity.get("id_star_system"),
            "arrival_system_id": sell_commodity.get("id_star_system"),
            "departure_planet_id": buy_commodity.get("id_planet"),
            "arrival_planet_id": sell_commodity.get("id_planet"),
            "commodity_id": buy_commodity.get("id_commodity"),
            "max_buyable_scu": max_buyable_scu,
            "distance": distance,
            "total_margin_by_distance": str(total_margin_by_distance),
            "unit_margin_by_distance": str(unit_margin_by_distance)
        }
        return route

    async def display_trade_routes(self, trade_routes, columns, quick=True):
        await self.ensure_initialized()
        nb_items = 5 if quick else self.page_items_combo.currentData()
        self.trade_route_table.setRowCount(0)  # Clear the table before adding sorted results
        trade_routes.sort(key=lambda x: float(x[self.sorting_options_combo.currentData()].split()[0]),
                          reverse=(self.sorting_order_combo.currentData() == "DESC"))
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
        for lineedit in self.findChildren(QLineEdit):
            lineedit.setEnabled(enabled)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.setEnabled(enabled)
        for combo in self.findChildren(QComboBox):
            combo.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)
