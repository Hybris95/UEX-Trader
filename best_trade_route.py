import logging
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QMessageBox, QTableWidgetItem,
    QHBoxLayout, QCheckBox, QApplication
)
from PyQt5.QtCore import Qt
import asyncio
from api import API
from config_manager import ConfigManager
from functools import partial
from trade_tab import TradeTab


class BestTradeRouteTab(QWidget):
    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.config_manager = ConfigManager()
        self.api = API(
            self.config_manager.get_api_key(),
            self.config_manager.get_secret_key(),
            self.config_manager.get_is_production(),
            self.config_manager.get_debug()
        )
        self.logger = logging.getLogger(__name__)
        self.terminals = []
        self.initUI()
        asyncio.ensure_future(self.load_systems())

    def initUI(self):
        layout = QVBoxLayout()
        self.max_scu_input = QLineEdit()
        self.max_scu_input.setPlaceholderText("Enter Max SCU")
        layout.addWidget(QLabel("Max SCU:"))
        layout.addWidget(self.max_scu_input)
        self.max_investment_input = QLineEdit()
        self.max_investment_input.setPlaceholderText("Enter Max Investment (UEC)")
        layout.addWidget(QLabel("Max Investment (UEC):"))
        layout.addWidget(self.max_investment_input)
        self.departure_system_combo = QComboBox()
        self.departure_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_departure_planets())
        )
        layout.addWidget(QLabel("Departure System:"))
        layout.addWidget(self.departure_system_combo)
        self.departure_planet_combo = QComboBox()
        self.departure_planet_combo.addItem("All Planets")
        self.departure_planet_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_departure_terminals())
        )
        layout.addWidget(QLabel("Departure Planet:"))
        layout.addWidget(self.departure_planet_combo)
        self.destination_system_combo = QComboBox()
        self.destination_system_combo.addItem("All Systems")
        self.destination_system_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_destination_planets())
        )
        layout.addWidget(QLabel("Destination System:"))
        layout.addWidget(self.destination_system_combo)
        self.destination_planet_combo = QComboBox()
        self.destination_planet_combo.addItem("All Planets")
        self.destination_planet_combo.currentIndexChanged.connect(
            lambda: asyncio.ensure_future(self.update_destination_terminals())
        )
        layout.addWidget(QLabel("Destination Planet:"))
        layout.addWidget(self.destination_planet_combo)
        self.ignore_stocks_checkbox = QCheckBox("Ignore Stocks")
        self.ignore_demand_checkbox = QCheckBox("Ignore Demand")
        layout.addWidget(self.ignore_stocks_checkbox)
        layout.addWidget(self.ignore_demand_checkbox)
        find_route_button = QPushButton("Find Best Trade Routes")
        find_route_button.clicked.connect(lambda: asyncio.ensure_future(self.find_best_trade_routes()))
        layout.addWidget(find_route_button)
        self.trade_route_table = QTableWidget()
        layout.addWidget(self.trade_route_table)
        self.setLayout(layout)

    async def load_systems(self):
        try:
            systems = await self.api.fetch_data("/star_systems")
            for system in systems.get("data", []):
                if system.get("is_available") == 1:
                    self.departure_system_combo.addItem(system["name"], system["id"])
                    self.destination_system_combo.addItem(system["name"], system["id"])
            logging.info("Systems loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load systems: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load systems: {e}")

    async def update_departure_planets(self):
        self.departure_planet_combo.clear()
        self.departure_planet_combo.addItem("All Planets")
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
            QMessageBox.critical(self, "Error", f"Failed to load departure planets: {e}")

    async def update_departure_terminals(self):
        self.terminals = []
        planet_id = self.departure_planet_combo.currentData()
        if not planet_id and self.departure_planet_combo.currentText() != "All Planets":
            return
        try:
            params = {'id_star_system': self.departure_system_combo.currentData()}
            if self.departure_planet_combo.currentText() != "All Planets":
                params['id_planet'] = planet_id
            terminals = await self.api.fetch_data("/terminals", params=params)
            self.terminals = [terminal for terminal in terminals.get("data", [])
                              if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
            logging.info("Departure terminals loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load departure terminals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load departure terminals: {e}")

    async def update_destination_planets(self):
        self.destination_planet_combo.clear()
        self.destination_planet_combo.addItem("All Planets")
        system_id = self.destination_system_combo.currentData()
        if not system_id and self.destination_system_combo.currentText() != "All Systems":
            return
        try:
            params = {}
            if self.destination_system_combo.currentText() != "All Systems":
                params['id_star_system'] = system_id
            planets = await self.api.fetch_data("/planets", params=params)
            for planet in planets.get("data", []):
                self.destination_planet_combo.addItem(planet["name"], planet["id"])
            logging.info("Destination planets loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load destination planets: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load destination planets: {e}")

    async def update_destination_terminals(self):
        self.destination_terminals = []
        planet_id = self.destination_planet_combo.currentData()
        if not planet_id and self.destination_planet_combo.currentText() != "All Planets":
            return
        try:
            params = {}
            if self.destination_system_combo.currentText() != "All Systems":
                params['id_star_system'] = self.destination_system_combo.currentData()
            if self.destination_planet_combo.currentText() != "All Planets":
                params['id_planet'] = planet_id
            terminals = await self.api.fetch_data("/terminals", params=params)
            self.destination_terminals = [terminal for terminal in terminals.get("data", [])
                                          if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
            logging.info("Destination terminals loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load destination terminals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load destination terminals: {e}")

    async def find_best_trade_routes(self):
        self.logger.log(logging.INFO, "Searching for Best Trade Routes")
        self.trade_route_table.setRowCount(0)  # Clear previous results
        columns = [
            "Departure", "Destination", "Commodity", "Buy SCU", "Buy Price",
            "Sell Price", "Investment", "Unit Margin", "Total Margin",
            "Departure SCU Available", "Arrival Demand SCU", "Profit Margin", "Actions"
        ]
        self.trade_route_table.setColumnCount(len(columns))
        self.trade_route_table.setHorizontalHeaderLabels(columns)

        try:
            max_scu, max_investment = self.get_input_values()
            departure_system_id, departure_planet_id, destination_system_id, destination_planet_id = self.get_selected_ids()

            if not departure_system_id:
                QMessageBox.warning(self, "Input Error", "Please Select a Departure System.")
                return

            departure_terminals = await self.fetch_terminals(departure_system_id, departure_planet_id)
            destination_terminals = []
            if not destination_system_id:
                all_systems = await self.fetch_systems(departure_system_id, 2)
                for system in all_systems:
                    # Fetch terminals for the current system with None as the destination_planet_id
                    terminals = await self.fetch_terminals(system["id"], None)
                    # Concatenate the fetched terminals into destination_terminals
                    destination_terminals.extend(terminals)
            else:
                destination_terminals = await self.fetch_terminals(destination_system_id, destination_planet_id)

            trade_routes = await self.calculate_trade_routes(departure_terminals,
                                                             destination_terminals, max_scu, max_investment)

            self.display_trade_routes(trade_routes, columns)

            self.logger.log(logging.INFO, "Finished calculating Best Trade Routes")

        except Exception as e:
            self.logger.log(logging.ERROR, f"An error occurred while finding best trade routes: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def get_input_values(self):
        max_scu = int(self.max_scu_input.text()) if self.max_scu_input.text() else sys.maxsize
        max_investment = float(self.max_investment_input.text()) if self.max_investment_input.text() else sys.maxsize
        return max_scu, max_investment

    def get_selected_ids(self):
        departure_system_id = self.departure_system_combo.currentData()
        departure_planet_id = self.departure_planet_combo.currentData()
        if self.departure_planet_combo.currentText() == "All Planets":
            departure_planet_id = None
        destination_system_id = self.destination_system_combo.currentData()
        destination_planet_id = self.destination_planet_combo.currentData()
        if self.destination_planet_combo.currentText() == "All Planets":
            destination_planet_id = None
        return departure_system_id, departure_planet_id, destination_system_id, destination_planet_id

    async def fetch_terminals(self, system_id, planet_id):
        params = {'id_star_system': system_id}
        if planet_id:
            params['id_planet'] = planet_id
        terminals = await self.api.fetch_data("/terminals", params=params)
        return [terminal for terminal in terminals.get("data", [])
                if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]

    async def fetch_systems(self, origin_system_id, max_bounce):
        params = {}
        # TODO - Return systems linked to origin_system_id with a maximum of "max_bounce" hops - API does not give this for now
        systems = await self.api.fetch_data("/star_systems", params=params)
        return [system for system in systems.get("data", [])
                if system.get("is_available") == 1]

    async def calculate_trade_routes(self, departure_terminals, destination_terminals, max_scu, max_investment):
        trade_routes = []
        for departure_terminal in departure_terminals:
            departure_commodities = await self.api.fetch_data("/commodities_prices",
                                                              params={'id_terminal': departure_terminal["id"]})
            self.logger.log(logging.INFO, f"Iterating through {len(departure_commodities.get('data', []))} \
                            commodities at departure terminal {departure_terminal['name']}")
            for departure_commodity in departure_commodities.get("data", []):
                if departure_commodity.get("price_buy") == 0:
                    continue
                arrival_commodities = await self.api.fetch_data("/commodities_prices",
                                                                params={'id_commodity':
                                                                        departure_commodity.get("id_commodity")})
                for arrival_terminal in destination_terminals:
                    trade_routes.extend(await self.process_trade_route(
                        departure_terminal, arrival_terminal, departure_commodity,
                        arrival_commodities, max_scu, max_investment
                    ))
                    # Allow UI to update during the search
                    QApplication.processEvents()
        return trade_routes

    async def process_trade_route(self, departure_terminal, arrival_terminal,
                                  departure_commodity, arrival_commodities, max_scu, max_investment):
        routes = []
        for arrival_commodity in arrival_commodities.get("data", []):
            if arrival_commodity.get("is_available") == 0 or arrival_commodity.get("id_terminal") == departure_terminal["id"]:
                continue

            available_scu = max_scu if self.ignore_stocks_checkbox.isChecked() else departure_commodity.get("scu_buy", 0)
            scu_sell_stock = arrival_commodity.get("scu_sell_stock", 0)
            scu_sell_users = arrival_commodity.get("scu_sell_users", 0)
            demand_scu = max_scu if self.ignore_demand_checkbox.isChecked() else scu_sell_stock - scu_sell_users

            price_buy = departure_commodity.get("price_buy")
            price_sell = arrival_commodity.get("price_sell")

            if not price_buy or not price_sell or available_scu <= 0 or not demand_scu:
                continue

            max_buyable_scu = min(max_scu, available_scu, int(max_investment // price_buy), demand_scu)
            if max_buyable_scu <= 0:
                continue

            investment = price_buy * max_buyable_scu
            unit_margin = (price_sell - price_buy)
            total_margin = unit_margin * max_buyable_scu
            profit_margin = unit_margin / price_buy

            routes.append({
                "departure": departure_terminal["name"],
                "destination": arrival_commodity["terminal_name"],
                "commodity": departure_commodity.get("commodity_name"),
                "buy_scu": f"{max_buyable_scu} SCU",
                "buy_price": f"{price_buy} UEC",
                "sell_price": f"{price_sell} UEC",
                "investment": f"{investment} UEC",
                "unit_margin": f"{unit_margin} UEC",
                "total_margin": f"{total_margin} UEC",
                "departure_scu_available": f"{departure_commodity.get('scu_buy', 0)} SCU",
                "arrival_demand_scu": f"{scu_sell_stock - scu_sell_users} SCU",
                "profit_margin": f"{round(profit_margin * 100)}%",
                "departure_terminal_id": departure_terminal["id"],
                "arrival_terminal_id": arrival_commodity.get("id_terminal"),
                "departure_system_id": departure_terminal.get("id_star_system"),
                "arrival_system_id": arrival_commodity.get("id_star_system"),
                "departure_planet_id": departure_terminal.get("id_planet"),
                "arrival_planet_id": arrival_commodity.get("id_planet"),
                "commodity_id": departure_commodity.get("id_commodity"),
                "max_buyable_scu": max_buyable_scu
            })
        return routes

    def display_trade_routes(self, trade_routes, columns):
        self.trade_route_table.setRowCount(0)  # Clear the table before adding sorted results
        trade_routes.sort(key=lambda x: float(x["total_margin"].split()[0]), reverse=True)
        for i, route in enumerate(trade_routes[:10]):
            self.trade_route_table.insertRow(i)
            for j, value in enumerate(route.values()):
                if j < len(columns) - 1:
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the item non-editable
                    self.trade_route_table.setItem(i, j, item)
                else:
                    self.add_action_buttons(i, j, trade_routes[i])

        # Resize columns to fit contents
        self.trade_route_table.resizeColumnsToContents()

    def add_action_buttons(self, i, j, trade_route):
        action_layout = QHBoxLayout()
        buy_button = QPushButton("Select to Buy")
        buy_button.clicked.connect(partial(self.select_to_buy, trade_route))
        sell_button = QPushButton("Select to Sell")
        sell_button.clicked.connect(partial(self.select_to_sell, trade_route))
        action_layout.addWidget(buy_button)
        action_layout.addWidget(sell_button)
        action_widget = QWidget()
        action_widget.setLayout(action_layout)
        self.trade_route_table.setCellWidget(i, j, action_widget)

    def select_to_buy(self, trade_route):
        self.logger.log(logging.INFO, "Selected route to buy")
        trade_tab = self.main_widget.findChild(TradeTab)
        if trade_tab:
            self.main_widget.loop.create_task(trade_tab.select_trade_route(trade_route, is_buy=True))
        else:
            self.logger.log(logging.ERROR, "An error occurred while selecting trade route")
            QMessageBox.critical(self, "Error", "An error occurred")

    def select_to_sell(self, trade_route):
        self.logger.log(logging.INFO, "Selected route to sell")
        trade_tab = self.main_widget.findChild(TradeTab)
        if trade_tab:
            self.main_widget.loop.create_task(trade_tab.select_trade_route(trade_route, is_buy=False))
        else:
            self.logger.log(logging.ERROR, "An error occurred while selecting trade route")
            QMessageBox.critical(self, "Error", "An error occurred")
