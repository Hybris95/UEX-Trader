import logging
import sys
import re
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
from tools import create_async_callback, days_difference_from_now, translate
import traceback


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
        self._terminals_unfiltered = []
        self.current_trades = []
        asyncio.ensure_future(self.load_systems())

    async def initialize(self):
        async with self._lock:
            if self.config_manager is None or self.translation_manager is None or self.api is None or self.columns is None:
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

    async def init_ui(self):
        layout = QVBoxLayout()
        self.max_scu_input = QLineEdit()
        self.max_scu_input.setPlaceholderText(await translate("enter") + " " + await translate("maximum")
                                              + " " + await translate("scu"))
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("scu") + ":"))
        layout.addWidget(self.max_scu_input)
        self.max_investment_input = QLineEdit()
        self.max_investment_input.setPlaceholderText(await translate("enter")
                                                     + " " + await translate("maximum")
                                                     + " " + await translate("investment")
                                                     + " (" + await translate("uec") + ")")
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("investment")
                                + " (" + await translate("uec") + "):"))
        layout.addWidget(self.max_investment_input)
        self.max_outdated_input = QLineEdit()
        self.max_outdated_input.setPlaceholderText(
            await translate("enter") + " " + await translate("maximum") + " " + await translate("outdated")
            + " (" + await translate("days") + ")")
        layout.addWidget(QLabel(await translate("maximum") + " " + await translate("outdated")
                                + " (" + await translate("days") + "):"))
        layout.addWidget(self.max_outdated_input)
        self.min_trade_profit_input = QLineEdit()
        self.min_trade_profit_input.setPlaceholderText(
            await translate("enter") + " " + await translate("minimum") + " " + await translate("trade_columns_total_margin")
            + " (" + await translate("uec") + ")")
        self.min_trade_profit_input.setText("8000")
        layout.addWidget(QLabel(await translate("minimum")
                                + " " + await translate("trade_columns_total_margin")
                                + " (" + await translate("uec") + "):"))
        layout.addWidget(self.min_trade_profit_input)
        self.departure_system_combo = QComboBox()
        self.departure_system_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_planets()))
        layout.addWidget(QLabel(await translate("departure_system") + ":"))
        layout.addWidget(self.departure_system_combo)
        self.departure_planet_combo = QComboBox()
        self.departure_planet_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_terminals()))
        layout.addWidget(QLabel(await translate("departure_planet") + ":"))
        layout.addWidget(self.departure_planet_combo)
        terminal_label = QLabel(await translate("select_terminal") + ":")
        self.terminal_filter_input = QLineEdit()
        self.terminal_filter_input.setPlaceholderText(await translate("filter_terminals"))
        self.terminal_filter_input.textChanged.connect(self.filter_terminals)
        self.departure_terminal_combo = QComboBox()
        layout.addWidget(terminal_label)
        layout.addWidget(self.terminal_filter_input)
        layout.addWidget(self.departure_terminal_combo)
        # Add checkboxes for filtering
        self.filter_system_checkbox = QCheckBox(await translate("filter_for_current_system"))
        self.filter_system_checkbox.setChecked(True)  # Ensure this checkbox is checked by default
        self.filter_planet_checkbox = QCheckBox(await translate("filter_for_current_planet"))
        layout.addWidget(self.filter_system_checkbox)
        layout.addWidget(self.filter_planet_checkbox)
        # Add checkboxes for ignoring stocks and demand
        self.ignore_stocks_checkbox = QCheckBox(await translate("ignore_stocks"))
        self.ignore_demand_checkbox = QCheckBox(await translate("ignore_demand"))
        layout.addWidget(self.ignore_stocks_checkbox)
        layout.addWidget(self.ignore_demand_checkbox)
        self.filter_public_hangars_checkbox = QCheckBox(await translate("no_public_hangars"))
        layout.addWidget(self.filter_public_hangars_checkbox)
        self.filter_space_only_checkbox = QCheckBox(await translate("space_only"))
        layout.addWidget(self.filter_space_only_checkbox)

        self.find_route_button = QPushButton(await translate("find_trade_route"))
        self.find_route_button.clicked.connect(lambda: asyncio.ensure_future(self.find_trade_routes()))
        layout.addWidget(self.find_route_button)

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
                                           + " (" + await translate("uec") + ")",
                                           "total_margin")
        self.sorting_options_combo.addItem(await translate("sort_profit_margin")
                                           + " (%)",
                                           "profit_margin")
        self.sorting_options_combo.addItem(await translate("sort_scu_margin")
                                           + " (" + await translate("uec") + "/" + await translate("scu") + ")",
                                           "unit_margin")
        self.sorting_options_combo.addItem(await translate("trade_columns_investment")
                                           + " (" + await translate("uec") + ")",
                                           "investment")
        self.sorting_options_combo.addItem(await translate("trade_columns_buy_scu")
                                           + " (" + await translate("unit_qty") + ")",
                                           "buy_scu")
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
        await self.define_columns()

    async def load_systems(self):
        try:
            await self.ensure_initialized()
            self.departure_system_combo.clear()
            for system in (await self.api.fetch_all_systems()):
                self.departure_system_combo.blockSignals(True)
                self.departure_system_combo.addItem(system["name"], system["id"])
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

    async def update_planets(self):
        await self.ensure_initialized()
        self.departure_planet_combo.clear()
        self.departure_terminal_combo.clear()
        self.terminal_filter_input.clear()  # Clear the filter input here
        self._terminals_unfiltered = []
        system_id = self.departure_system_combo.currentData()
        if not system_id:
            return
        try:
            for planet in (await self.api.fetch_planets(system_id)):
                self.departure_planet_combo.addItem(planet["name"], planet["id"])
            self.departure_planet_combo.addItem(await translate("unknown_planet"), 0)
            logging.info("Planets loaded successfully for star_system ID : %s", system_id)
        except Exception as e:
            logging.error("Failed to load planets: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_failed_to_load_planets") + f": {e}")

    async def update_terminals(self):
        await self.ensure_initialized()
        self.departure_terminal_combo.clear()
        self.terminal_filter_input.clear()  # Ensure the filter input is cleared when updating terminals
        self._terminals_unfiltered = []
        planet_id = self.departure_planet_combo.currentData()
        system_id = self.departure_system_combo.currentData()
        try:
            if not planet_id:
                if system_id:
                    self._terminals_unfiltered = [terminal for terminal in (await self.api.fetch_terminals(system_id))
                                                  if terminal.get("id_planet") == 0]
                    logging.info("Terminals loaded successfully for system ID (Unknown planet): %s", system_id)
            else:
                self._terminals_unfiltered = await self.api.fetch_terminals_from_planet(planet_id)
                logging.info("Terminals loaded successfully for planet ID : %s", planet_id)
        except Exception as e:
            logging.error("Failed to load terminals: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_failed_to_load_terminals") + f": {e}")
        finally:
            self.filter_terminals()

    async def update_page_items(self):
        await self.ensure_initialized()
        await self.update_trade_route_table(self.current_trades, self.columns, quick=False)

    def filter_terminals(self):
        filter_text = self.terminal_filter_input.text().lower()
        self.departure_terminal_combo.clear()
        for terminal in self._terminals_unfiltered:
            if filter_text in terminal["name"].lower():
                self.departure_terminal_combo.addItem(terminal["name"], terminal["id"])

    async def define_columns(self):
        self.columns = [
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
            await translate("trade_columns_actions")
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
            await self.validate_inputs()
            self.current_trades = await self.fetch_and_process_departure_commodities()

            await self.update_trade_route_table(self.current_trades, self.columns, quick=False)
        except ValueError as e:
            self.logger.warning("Input Error: %s", e)
            QMessageBox.warning(self, await translate("error_input_error"), str(e))
        except Exception as e:
            self.logger.error("An error occurred while finding trade routes: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            QMessageBox.critical(self, await translate("error_error"),
                                 await translate("error_generic") + f": {e}")
        finally:
            await self.main_widget.set_gui_enabled(True)
            self.progress_bar.setVisible(False)
            self.main_progress_bar.setVisible(False)

    def get_validated_inputs(self):
        max_scu = int(self.max_scu_input.text()) if self.max_scu_input.text() else sys.maxsize
        max_investment = float(self.max_investment_input.text()) if self.max_investment_input.text() else sys.maxsize
        max_outdated_days = int(self.max_outdated_input.text()) if self.max_outdated_input.text() else sys.maxsize
        min_trade_profit = int(self.min_trade_profit_input.text()) if self.min_trade_profit_input.text() else 0
        return max_scu, max_investment, max_outdated_days, min_trade_profit

    def get_ids(self):
        departure_system_id = self.departure_system_combo.currentData()
        departure_planet_id = self.departure_planet_combo.currentData()
        departure_terminal_id = self.departure_terminal_combo.currentData()
        return departure_system_id, departure_planet_id, departure_terminal_id

    async def validate_inputs(self):
        await self.ensure_initialized()
        if not re.match(r'^\d+$', self.max_scu_input.text()) and self.max_scu_input.text() != "":
            raise ValueError(await translate("scu") + " " + await translate("error_input_invalid_integer"))
        if not re.match(r'^\d+(\.\d+)?$', self.max_investment_input.text()) and self.max_investment_input.text() != "":
            raise ValueError(await translate("max_investment") + " " + await translate("error_input_invalid_number"))
        if not re.match(r'^\d+$', self.max_outdated_input.text()) and self.max_outdated_input.text() != "":
            raise ValueError(await translate("days") + " " + await translate("error_input_invalid_integer"))
        if not re.match(r'^\d+$', self.min_trade_profit_input.text()) and self.min_trade_profit_input.text() != "":
            raise ValueError(await translate("trade_columns_profit_margin")
                             + " " + await translate("error_input_invalid_integer"))
        ids = self.get_ids()
        departure_system_id = ids[0]
        departure_terminal_id = ids[2]
        if not all([departure_system_id, departure_terminal_id]):
            raise ValueError(await translate("error_input_select_dpt"))
        return

    async def fetch_and_process_departure_commodities(self):
        await self.ensure_initialized()
        trade_routes = []
        departure_terminal_id = self.get_ids()[2]
        departure_commodities = await self.api.fetch_commodities_from_terminal(departure_terminal_id)
        universe = len(departure_commodities)
        self.logger.info("Iterating through %s commodities at departure terminal", universe)
        self.main_progress_bar.setMaximum(universe)
        action_progress = 0
        for departure_commodity in departure_commodities:
            self.main_progress_bar.setValue(action_progress)
            action_progress += 1
            if departure_commodity.get("price_buy") == 0:
                continue
            arrival_commodities = await self.api.fetch_commodities_by_id(departure_commodity.get("id_commodity"))
            self.logger.info("Found %s terminals that might sell %s",
                             len(arrival_commodities),
                             departure_commodity.get('commodity_name'))
            trade_routes.extend(await self.process_arrival_commodities(arrival_commodities, departure_commodity))
            await self.update_trade_route_table(trade_routes, self.columns)
        self.main_progress_bar.setValue(action_progress)
        return trade_routes

    async def process_arrival_commodities(self, arrival_commodities, departure_commodity):
        await self.ensure_initialized()
        departure_system_id, departure_planet_id, departure_terminal_id = self.get_ids()
        trade_routes = []
        universe = len(arrival_commodities)
        self.progress_bar.setMaximum(universe)
        action_progress = 0
        for arrival_commodity in arrival_commodities:
            self.progress_bar.setValue(action_progress)
            action_progress += 1
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
            trade_route = await self.calculate_trade_route_details(arrival_commodity, departure_commodity)
            if trade_route:
                trade_routes.append(trade_route)
        self.progress_bar.setValue(action_progress)
        return trade_routes

    async def calculate_trade_route_details(self, arrival_commodity, departure_commodity):
        await self.ensure_initialized()
        max_scu, max_investment, max_outdated_days, min_trade_profit = self.get_validated_inputs()
        departure_system_id, departure_planet_id, departure_terminal_id = self.get_ids()
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
        arrival_id_star_system = arrival_commodity.get("id_star_system")
        destination = next(
            (system["name"] for system in (await self.api.fetch_system(arrival_id_star_system))),
            translate("unknown_system"))
        + " - " + next(
            (planet["name"] for planet in (await self.api.fetch_planets(arrival_id_star_system,
                                                                        arrival_commodity.get("id_planet")))),
            translate("unknown_planet"))
        + " / " + arrival_commodity.get("terminal_name")
        distance = await self.api.fetch_distance(departure_commodity["id_terminal"],
                                                 arrival_commodity["id_terminal"],
                                                 departure_commodity["id_commodity"])
        total_margin_by_distance = total_margin / distance
        unit_margin_by_distance = unit_margin / distance
        return {
            "destination": destination,
            "commodity": departure_commodity.get("commodity_name"),
            "buy_scu": str(max_buyable_scu) + " " + await translate("scu"),
            "buy_price": str(buy_price) + " " + await translate("uec"),
            "sell_price": str(sell_price) + " " + await translate("uec"),
            "investment": str(investment) + " " + await translate("uec"),
            "unit_margin": str(unit_margin) + " " + await translate("uec"),
            "total_margin": str(total_margin) + " " + await translate("uec"),
            "departure_scu_available": str(original_available_scu) + " " + await translate("scu"),
            "arrival_demand_scu": str(original_demand_scu) + " " + await translate("scu"),
            "profit_margin": str(round(profit_margin * 100)) + " %",
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
        nb_items = 5 if quick else self.page_items_combo.currentData()
        trade_routes.sort(key=lambda x: float(x[self.sorting_options_combo.currentData()].split()[0]),
                          reverse=(self.sorting_order_combo.currentData() == "DESC"))
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
                    buy_button = QPushButton(await translate("select_to_buy"))
                    buy_button.clicked.connect(create_async_callback(self.select_to_buy, trade_routes[i]))
                    sell_button = QPushButton(await translate("select_to_sell"))
                    sell_button.clicked.connect(create_async_callback(self.select_to_sell, trade_routes[i]))
                    action_layout.addWidget(buy_button)
                    action_layout.addWidget(sell_button)
                    action_widget = QWidget()
                    action_widget.setLayout(action_layout)
                    self.trade_route_table.setCellWidget(i, j, action_widget)
        if len(trade_routes) == 0:
            self.trade_route_table.insertRow(0)
            item = QTableWidgetItem(await translate("no_results_found"))
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
