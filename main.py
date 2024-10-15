import sys
import asyncio
import logging
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QMessageBox,
    QTabWidget,
)
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtCore import Qt
import configparser
import aiohttp
import re

API_BASE_URL = "https://uexcorp.space/api/2.0"

class ConfigManager:
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        self.config.read(self.config_file)

    def save_config(self):
        with open(self.config_file, "w") as f:
            self.config.write(f)

    def get_api_key(self):
        return self.config.get("API", "key", fallback="")

    def set_api_key(self, key):
        self.config["API"] = {"key": key}
        self.save_config()

    def get_is_production(self):
        return self.config.getboolean("SETTINGS", "is_production", fallback=False)

    def set_is_production(self, is_production):
        self.config["SETTINGS"] = {"is_production": str(is_production)}
        self.save_config()

    def get_debug(self):
        return self.config.getboolean("SETTINGS", "debug", fallback=False)

    def set_debug(self, debug):
        self.config["SETTINGS"]["debug"] = str(debug)
        self.save_config()


class UexcorpTrader(QWidget):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.api_key = self.config_manager.get_api_key()
        self.is_production = self.config_manager.get_is_production()
        self.debug = self.config_manager.get_debug()

        # Configure logging based on the debug setting
        logging_level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(level=logging_level, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        self.star_systems = []
        self.planets = []
        self.terminals = []
        self.commodities = []

        self.initUI()

    def initUI(self):
        self.logger.debug("Initializing UI")
        self.setWindowTitle("UEXcorp Trader")
        self.showFullScreen()

        tabs = QTabWidget()
        tabs.addTab(self.create_config_tab(), "Configuration")
        tabs.addTab(self.create_trade_tab("Buy Commodity", self.buy_commodity), "Buy Commodity")
        tabs.addTab(self.create_trade_tab("Sell Commodity", self.sell_commodity), "Sell Commodity")

        main_layout = QVBoxLayout()
        main_layout.addWidget(tabs)
        self.setLayout(main_layout)

        asyncio.ensure_future(self.load_data())

    def create_config_tab(self):
        self.logger.debug("Creating configuration tab")
        config_tab = QWidget()
        layout = QVBoxLayout()

        api_key_label = QLabel("UEXcorp API Key:")
        self.api_key_input = QLineEdit(self.api_key)

        is_production_label = QLabel("Is Production:")
        self.is_production_input = QComboBox()
        self.is_production_input.addItems(["False", "True"])
        self.is_production_input.setCurrentText(str(self.is_production))

        debug_label = QLabel("Debug Mode:")
        self.debug_input = QComboBox()
        self.debug_input.addItems(["False", "True"])
        self.debug_input.setCurrentText(str(self.debug))

        save_config_button = QPushButton("Save Configuration")
        save_config_button.clicked.connect(self.save_configuration)

        layout.addWidget(api_key_label)
        layout.addWidget(self.api_key_input)
        layout.addWidget(is_production_label)
        layout.addWidget(self.is_production_input)
        layout.addWidget(debug_label)
        layout.addWidget(self.debug_input)
        layout.addWidget(save_config_button)

        config_tab.setLayout(layout)
        return config_tab

    def create_trade_tab(self, title, trade_function):
        self.logger.debug(f"Creating trade tab: {title}")
        trade_tab = QWidget()
        layout = QVBoxLayout()

        system_label = QLabel("Select System:")
        system_combo = QComboBox()
        system_combo.currentIndexChanged.connect(lambda: self.update_planets(system_combo))
        layout.addWidget(system_label)
        layout.addWidget(system_combo)

        planet_label = QLabel("Select Planet:")
        planet_combo = QComboBox()
        planet_combo.currentIndexChanged.connect(lambda: self.update_terminals(planet_combo))
        layout.addWidget(planet_label)
        layout.addWidget(planet_combo)

        terminal_label = QLabel("Select Terminal:")
        terminal_combo = QComboBox()
        terminal_combo.currentIndexChanged.connect(lambda: self.update_commodities(terminal_combo))
        layout.addWidget(terminal_label)
        layout.addWidget(terminal_combo)

        commodity_label = QLabel("Select Commodity:")
        commodity_combo = QComboBox()
        commodity_combo.currentIndexChanged.connect(lambda: self.update_price(commodity_combo, terminal_combo))
        layout.addWidget(commodity_label)
        layout.addWidget(commodity_combo)

        amount_label = QLabel("Amount (SCU):")
        amount_input = QLineEdit()
        amount_input.setValidator(QIntValidator(0, 1000000))  # Allow only integers
        price_label = QLabel("Price (UEC/SCU):")
        price_input = QLineEdit()
        price_input.setValidator(QDoubleValidator(0.0, 1000000.0, 2))  # Allow only floating-point numbers with 2 decimal places
        layout.addWidget(amount_label)
        layout.addWidget(amount_input)
        layout.addWidget(price_label)
        layout.addWidget(price_input)

        trade_button = QPushButton(title)
        trade_button.clicked.connect(lambda: asyncio.ensure_future(trade_function(system_combo, planet_combo, terminal_combo, commodity_combo, amount_input, price_input)))
        layout.addWidget(trade_button)

        trade_tab.setLayout(layout)
        return trade_tab

    async def load_data(self):
        self.logger.debug("Loading data")
        try:
            async with aiohttp.ClientSession() as session:
                self.star_systems = await self.fetch_data(session, "/star_systems")
                self.log_api_output(f"Star Systems Loaded: {self.star_systems}", level=logging.INFO)
                self.update_system_combos()

        except Exception as e:
            self.log_api_output(f"Error loading initial data: {e}", level=logging.ERROR)

    async def fetch_data(self, session, endpoint, params=None):
        url = f"{API_BASE_URL}{endpoint}"
        self.log_api_output(f"API Request: GET {url} {params if params else ''}", level=logging.DEBUG)
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_api_output(f"API Response: {data}", level=logging.DEBUG)
                    return data
                else:
                    error_message = await response.text()
                    self.log_api_output(f"API request failed with status {response.status}: {error_message}", level=logging.ERROR)
                    return []
        except Exception as e:
            self.log_api_output(f"Error during API request to {url}: {e}", level=logging.ERROR)
            return []

    def update_system_combos(self):
        self.log_api_output("Updating system combos...", level=logging.INFO)
        for combo in [self.findChild(QComboBox, "system_combo"), self.findChild(QComboBox, "sell_system_combo")]:
            if combo:
                combo.clear()
                for star_system in self.star_systems.get("data", []):
                    if star_system.get("is_available") == 1:
                        combo.addItem(star_system["name"], star_system["id"])
        self.log_api_output("System combos updated.", level=logging.INFO)

    def update_planets(self, system_combo):
        self.logger.debug("Updating planets")
        system_id = system_combo.currentData()
        if system_id:
            asyncio.ensure_future(self.update_planets_async(system_id, system_combo))

    async def update_planets_async(self, system_id, system_combo):
        self.logger.debug("Updating planets asynchronously")
        try:
            async with aiohttp.ClientSession() as session:
                self.planets = await self.fetch_data(session, "/planets", params={'id_star_system': system_id})
                self.update_planet_combo(system_combo)
        except Exception as e:
            self.log_api_output(f"Error loading planets: {e}", level=logging.ERROR)

    def update_planet_combo(self, system_combo):
        self.logger.debug("Updating planet combo")
        planet_combo = system_combo.parent().findChild(QComboBox, "planet_combo")
        if planet_combo:
            planet_combo.clear()
            for planet in self.planets:
                planet_combo.addItem(planet["name"], planet["id"])

    def update_terminals(self, planet_combo):
        self.logger.debug("Updating terminals")
        planet_id = planet_combo.currentData()
        if planet_id:
            asyncio.ensure_future(self.update_terminals_async(planet_id, planet_combo))

    async def update_terminals_async(self, planet_id, planet_combo):
        self.logger.debug("Updating terminals asynchronously")
        try:
            async with aiohttp.ClientSession() as session:
                self.terminals = await self.fetch_data(session, "/terminals", params={'id_planet': planet_id})
                self.update_terminal_combo(planet_combo)
        except Exception as e:
            self.log_api_output(f"Error loading terminals: {e}", level=logging.ERROR)

    def update_terminal_combo(self, planet_combo):
        self.logger.debug("Updating terminal combo")
        terminal_combo = planet_combo.parent().findChild(QComboBox, "terminal_combo")
        if terminal_combo:
            terminal_combo.clear()
            for terminal in self.terminals:
                terminal_combo.addItem(terminal["name"], terminal["id"])

    def update_commodities(self, terminal_combo):
        self.logger.debug("Updating commodities")
        terminal_id = terminal_combo.currentData()
        if terminal_id:
            asyncio.ensure_future(self.update_commodities_async(terminal_id, terminal_combo))

    async def update_commodities_async(self, terminal_id, terminal_combo):
        self.logger.debug("Updating commodities asynchronously")
        try:
            async with aiohttp.ClientSession() as session:
                self.commodities = await self.fetch_data(session, "/commodities_prices", params={'id_terminal': terminal_id})
                self.update_commodity_combo(terminal_combo)
        except Exception as e:
            self.log_api_output(f"Error loading commodities: {e}", level=logging.ERROR)

    def update_commodity_combo(self, terminal_combo):
        self.logger.debug("Updating commodity combo")
        commodity_combo = terminal_combo.parent().findChild(QComboBox, "commodity_combo")
        if commodity_combo:
            commodity_combo.clear()
            for commodity in self.commodities:
                commodity_combo.addItem(commodity["commodity_name"], commodity["id_commodity"])

    def update_price(self, commodity_combo, terminal_combo):
        self.logger.debug("Updating price")
        commodity_id = commodity_combo.currentData()
        terminal_id = terminal_combo.currentData()
        if commodity_id and terminal_id:
            asyncio.ensure_future(self.update_price_async(commodity_id, terminal_id, commodity_combo))

    async def update_price_async(self, commodity_id, terminal_id, commodity_combo):
        self.logger.debug("Updating price asynchronously")
        try:
            async with aiohttp.ClientSession() as session:
                prices = await self.fetch_data(session, "/commodities_prices", params={'id_commodity': commodity_id, 'id_terminal': terminal_id})
                if prices:
                    price_input = commodity_combo.parent().findChild(QLineEdit, "price_input")
                    if price_input:
                        price_input.setText(str(prices[0]["price_sell"] if prices[0]["price_sell"] else prices[0]["price_buy"]))
        except Exception as e:
            self.log_api_output(f"Error loading prices: {e}", level=logging.ERROR)

    def save_configuration(self):
        self.logger.debug("Saving configuration")
        self.api_key = self.api_key_input.text()
        self.config_manager.set_api_key(self.api_key)
        self.is_production = self.is_production_input.currentText() == "True"
        self.config_manager.set_is_production(self.is_production)
        self.debug = self.debug_input.currentText() == "True"
        self.config_manager.set_debug(self.debug)

        # Reconfigure logging based on the new debug setting
        logging_level = logging.DEBUG if self.debug else logging.INFO
        logging.getLogger().setLevel(logging_level)

        QMessageBox.information(self, "Configuration", "Configuration saved successfully!")

    async def buy_commodity(self, system_combo, planet_combo, terminal_combo, commodity_combo, amount_input, price_input):
        self.logger.debug("Buying commodity")
        await self.perform_trade("buy", system_combo, planet_combo, terminal_combo, commodity_combo, amount_input, price_input)

    async def sell_commodity(self, system_combo, planet_combo, terminal_combo, commodity_combo, amount_input, price_input):
        self.logger.debug("Selling commodity")
        await self.perform_trade("sell", system_combo, planet_combo, terminal_combo, commodity_combo, amount_input, price_input)

    async def perform_trade(self, operation, system_combo, planet_combo, terminal_combo, commodity_combo, amount_input, price_input):
        self.logger.debug(f"Performing trade: {operation}")
        try:
            terminal_id = terminal_combo.currentData()
            commodity_id = commodity_combo.currentData()
            amount = amount_input.text()
            price = price_input.text()

            if not all([terminal_id, commodity_id, amount, price]):
                raise ValueError("Please fill all fields.")

            if not re.match(r'^\d+$', amount):
                raise ValueError("Amount must be a valid integer.")

            if not re.match(r'^\d+(\.\d{1,2})?$', price):
                raise ValueError("Price must be a valid number with up to 2 decimal places.")

            # Validate terminal and commodity
            if not any(terminal["id"] == terminal_id for terminal in self.terminals):
                raise ValueError("Selected terminal does not exist.")
            if not any(commodity["id_commodity"] == commodity_id for commodity in self.commodities):
                raise ValueError("Selected commodity does not exist on this terminal.")

            data = {
                "id_terminal": terminal_id,
                "id_commodity": commodity_id,
                "operation": operation,
                "scu": int(amount),
                "price": float(price),
                "is_production": int(self.is_production),  # Use the loaded configuration boolean
            }

            self.log_api_output(f"API Request: POST {API_BASE_URL}/user_trades_add/ {data}", level=logging.INFO)
            async with aiohttp.ClientSession(headers={"secret_key": self.api_key}) as session:
                async with session.post(f"{API_BASE_URL}/user_trades_add/", json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        QMessageBox.information(self, "Success", f"Trade successful! Trade ID: {result.get('id_user_trade')}")
                    else:
                        error_message = await response.text()
                        self.log_api_output(f"API request failed with status {response.status}: {error_message}", level=logging.ERROR)
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def log_api_output(self, message, level=logging.INFO):
        self.logger.log(level, message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    trader = UexcorpTrader()
    trader.show()
    sys.exit(app.exec_())
