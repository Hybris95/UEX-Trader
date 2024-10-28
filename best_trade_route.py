import logging
import sys
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QMessageBox, QTableWidgetItem, QHBoxLayout, QCheckBox
from PyQt5.QtCore import Qt
import asyncio
from api import API
from config_manager import ConfigManager
from functools import partial
from trade_tab import TradeTab  # Import TradeTab

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
        self.departure_system_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_departure_planets()))
        layout.addWidget(QLabel("Departure System:"))
        layout.addWidget(self.departure_system_combo)

        self.departure_planet_combo = QComboBox()
        self.departure_planet_combo.addItem("All Planets")  # Option to ignore source planet
        self.departure_planet_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_departure_terminals()))
        layout.addWidget(QLabel("Departure Planet:"))
        layout.addWidget(self.departure_planet_combo)

        self.destination_system_combo = QComboBox()
        self.destination_system_combo.addItem("All Systems")  # Option to ignore specific destination system
        self.destination_system_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_destination_planets()))
        layout.addWidget(QLabel("Destination System:"))
        layout.addWidget(self.destination_system_combo)

        self.destination_planet_combo = QComboBox()
        self.destination_planet_combo.addItem("All Planets")  # Option to ignore destination planet
        self.destination_planet_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_destination_terminals()))
        layout.addWidget(QLabel("Destination Planet:"))
        layout.addWidget(self.destination_planet_combo)

        # Add checkboxes for ignoring stocks and demand
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
        self.departure_planet_combo.addItem("All Planets")  # Option to ignore source planet
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
            self.terminals = [terminal for terminal in terminals.get("data", []) if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
            logging.info("Departure terminals loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load departure terminals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load departure terminals: {e}")

    async def update_destination_planets(self):
        self.destination_planet_combo.clear()
        self.destination_planet_combo.addItem("All Planets")  # Option to ignore destination planet
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
            self.destination_terminals = [terminal for terminal in terminals.get("data", []) if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]
            logging.info("Destination terminals loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load destination terminals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load destination terminals: {e}")

    async def find_best_trade_routes(self):
        self.logger.log(logging.INFO, "Searching for Best Trade Routes")
        self.trade_route_table.setRowCount(0)  # Clear previous results

        # Define the columns
        columns = [
            "Departure", "Destination", "Commodity", "Buy SCU", "Buy Price", "Sell Price",
            "Investment", "Unit Margin", "Total Margin", "Departure SCU Available",
            "Arrival Demand SCU", "Profit Margin", "Actions"
        ]
        self.trade_route_table.setColumnCount(len(columns))
        self.trade_route_table.setHorizontalHeaderLabels(columns)

        try:
            max_scu = int(self.max_scu_input.text()) if self.max_scu_input.text() else sys.maxsize
            max_investment = float(self.max_investment_input.text()) if self.max_investment_input.text() else sys.maxsize
            departure_system_id = self.departure_system_combo.currentData()
            departure_planet_id = self.departure_planet_combo.currentData() if self.departure_planet_combo.currentText() != "All Planets" else None
            destination_system_id = self.destination_system_combo.currentData() if self.destination_system_combo.currentText() != "All Systems" else None
            destination_planet_id = self.destination_planet_combo.currentData() if self.destination_planet_combo.currentText() != "All Planets" else None

            # Basic input validation
            if not departure_system_id:
                QMessageBox.warning(self, "Input Error", "Please Select a Departure System.")
                return

            # Fetch all commodities to find the best trade routes
            commodities = await self.api.fetch_data("/commodities")
            if not commodities or "data" not in commodities:
                self.logger.log(logging.INFO, "No commodities found.")
                self.trade_route_table.insertRow(0)
                item = QTableWidgetItem("No results found")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the item non-editable
                self.trade_route_table.setItem(0, 0, item)
                return

            trade_routes = []
            for commodity in commodities["data"]:
                # Fetch trade routes using the /commodities_routes endpoint
                params = {'id_commodity': commodity["id"]}
                trade_routes_data = await self.api.fetch_data("/commodities_routes", params=params)
                if isinstance(trade_routes_data, dict):
                    trade_routes_data = trade_routes_data.get("data", [])

                for route in trade_routes_data:
                    # Filter routes based on selected source and destination systems and planets
                    if departure_system_id and route["id_star_system_origin"] != departure_system_id:
                        continue
                    if departure_planet_id and route["id_planet_origin"] != departure_planet_id:
                        continue
                    if destination_system_id and route["id_star_system_destination"] != destination_system_id:
                        continue
                    if destination_planet_id and route["id_planet_destination"] != destination_planet_id:
                        continue

                    # Apply filters if checkboxes are checked
                    if self.ignore_stocks_checkbox.isChecked():
                        available_scu = max_scu
                    else:
                        available_scu = route.get("scu_origin", 0)

                    if self.ignore_demand_checkbox.isChecked():
                        demand_scu = max_scu
                    else:
                        demand_scu = route.get("scu_destination", 0)

                    # Skip if buy or sell price is 0 or if SCU requirements aren't met
                    if not route.get("price_origin") or not route.get("price_destination") or available_scu <= 0 or not demand_scu:
                        continue

                    max_buyable_scu = min(max_scu, available_scu, int(max_investment // route.get("price_origin")), demand_scu)
                    if max_buyable_scu <= 0:
                        continue

                    investment = route.get("price_origin") * max_buyable_scu
                    unit_margin = (route.get("price_destination") - route.get("price_origin"))
                    total_margin = unit_margin * max_buyable_scu
                    profit_margin = unit_margin / route.get("price_origin")

                    trade_routes.append({
                        "departure": route["origin_terminal_name"],
                        "destination": route["destination_terminal_name"],
                        "commodity": route["commodity_name"],
                        "buy_scu": str(max_buyable_scu) + " SCU",
                        "buy_price": str(route.get("price_origin")) + " UEC",
                        "sell_price": str(route.get("price_destination")) + " UEC",
                        "investment": str(investment) + " UEC",
                        "unit_margin": str(unit_margin) + " UEC",
                        "total_margin": str(total_margin) + " UEC",
                        "departure_scu_available": str(route.get("scu_origin", 0)) + " SCU",
                        "arrival_demand_scu": str(route.get("scu_destination", 0)) + " SCU",
                        "profit_margin": str(round(profit_margin * 100)) + "%",
                        "departure_terminal_id": route["id_terminal_origin"],
                        "arrival_terminal_id": route["id_terminal_destination"],
                        "departure_system_id": route["id_star_system_origin"],
                        "arrival_system_id": route["id_star_system_destination"],
                        "departure_planet_id": route["id_planet_origin"],
                        "arrival_planet_id": route["id_planet_destination"],
                        "commodity_id": route["id_commodity"],
                        "max_buyable_scu": max_buyable_scu
                    })

            # Sort trade routes by profit margin (descending)
            trade_routes.sort(key=lambda x: float(x["total_margin"].split()[0]), reverse=True)

            # Display up to the top 10 results
            self.trade_route_table.setRowCount(0)  # Clear the table before adding sorted results
            for i, route in enumerate(trade_routes[:10]):
                self.trade_route_table.insertRow(i)
                for j, value in enumerate(route.values()):
                    if j < len(columns) - 1:
                        item = QTableWidgetItem(str(value))
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the item non-editable
                        self.trade_route_table.setItem(i, j, item)
                    else:
                        # Add action buttons
                        action_layout = QHBoxLayout()
                        buy_button = QPushButton("Select to Buy")
                        buy_button.clicked.connect(partial(self.select_to_buy, trade_routes[i]))
                        sell_button = QPushButton("Select to Sell")
                        sell_button.clicked.connect(partial(self.select_to_sell, trade_routes[i]))
                        action_layout.addWidget(buy_button)
                        action_layout.addWidget(sell_button)
                        action_widget = QWidget()
                        action_widget.setLayout(action_layout)
                        self.trade_route_table.setCellWidget(i, j, action_widget)

            if len(trade_routes) == 0:
                self.trade_route_table.insertRow(0)
                item = QTableWidgetItem("No results found")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the item non-editable
                self.trade_route_table.setItem(0, 0, item)

            # Resize columns to fit contents
            self.trade_route_table.resizeColumnsToContents()

            self.logger.log(logging.INFO, "Finished calculating Best Trade routes")
        except Exception as e:
            self.logger.log(logging.ERROR, f"An error occurred while finding best trade routes: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def select_to_buy(self, trade_route):
        self.logger.log(logging.INFO, "Selected route to buy")
        trade_tab = self.main_widget.findChild(TradeTab)
        if trade_tab:
            self.main_widget.loop.create_task(trade_tab.select_trade_route(trade_route, is_buy=True))
        else:
            self.logger.log(logging.ERROR, f"An error occurred while selecting trade route")
            QMessageBox.critical(self, "Error", f"An error occurred")

    def select_to_sell(self, trade_route):
        self.logger.log(logging.INFO, "Selected route to sell")
        trade_tab = self.main_widget.findChild(TradeTab)
        if trade_tab:
            self.main_widget.loop.create_task(trade_tab.select_trade_route(trade_route, is_buy=False))
        else:
            self.logger.log(logging.ERROR, f"An error occurred while selecting trade route")
            QMessageBox.critical(self, "Error", f"An error occurred")
