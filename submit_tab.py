# submit_tab.py
import asyncio
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt5.QtWidgets import QLabel, QLineEdit, QComboBox, QPushButton
import traceback
import logging
from api import API
from config_manager import ConfigManager
from translation_manager import TranslationManager
from tools import translate


class SubmitTab(QWidget):
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

    async def initialize(self):
        async with self._lock:
            if not self._initialized.is_set():
                self.config_manager = await ConfigManager.get_instance()
                self.api = await API.get_instance(self.config_manager)
                self.translation_manager = await TranslationManager.get_instance()
                await self.init_ui()
                self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def init_ui(self):
        self.main_layout = QVBoxLayout()
        await self.prep_system()
        await self.prep_planet()
        await self.prep_terminal()
        await self.prep_table()
        await self.prep_add_commodity()
        self.add_widgets()
        self.setLayout(self.main_layout)

    async def prep_system(self):
        self.system_label = QLabel(await translate("select_system") + ":")
        self.system_combo = QComboBox()
        self.system_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_planets()))

    async def prep_planet(self):
        self.planet_label = QLabel(await translate("select_planet") + ":")
        self.planet_combo = QComboBox()
        self.planet_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_terminals()))

    async def prep_terminal(self):
        self.terminal_label = QLabel(await translate("select_terminal") + ":")
        self.terminal_filter_input = QLineEdit()
        self.terminal_filter_input.setPlaceholderText(await translate("filter_terminals"))
        self.terminal_filter_input.textChanged.connect(self.filter_terminals)
        self.terminal_combo = QComboBox()
        self.terminal_combo.currentIndexChanged.connect(lambda: asyncio.ensure_future(self.update_commodities()))

    async def prep_table(self):
        raise NotImplementedError()  # TODO - Prepare entry table

    async def prep_add_commodity(self):
        raise NotImplementedError()  # TODO - Prepare the button to add a new commodity

    def add_widgets(self):
        self.main_layout.addWidget(self.system_label)
        self.main_layout.addWidget(self.system_combo)
        self.main_layout.addWidget(self.planet_label)
        self.main_layout.addWidget(self.planet_combo)
        self.main_layout.addWidget(self.terminal_label)
        self.main_layout.addWidget(self.terminal_filter_input)
        self.main_layout.addWidget(self.terminal_combo)
        raise NotImplementedError()  # TODO - Add entry table
        raise NotImplementedError()  # TODO - Add the button to add a new commodity

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

    async def update_terminals(self):
        await self.ensure_initialized()
        self.terminal_combo.clear()
        self.terminal_filter_input.clear()
        self._unfiltered_terminals = []
        planet_id = self.planet_combo.currentData()
        system_id = self.system_combo.currentData()
        try:
            if not planet_id:
                if system_id:
                    self._unfiltered_terminals = [terminal for terminal in (await self.api.fetch_terminals(system_id))
                                                  if terminal.get("id_planet") == 0]
                    logging.info("Terminals loaded successfully for system ID (Unknown planet): %s", system_id)
            else:
                self._unfiltered_terminals = await self.api.fetch_terminals_from_planet(planet_id)
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

    async def update_commodities(self):
        await self.ensure_initialized()
        raise NotImplementedError()  # TODO - Erase current list of commodities shown in the table
        terminal_id = self.terminal_combo.currentData()
        if not terminal_id:
            return
        try:
            self._current_terminal_commodities = await self.api.fetch_commodities_from_terminal(terminal_id)
            for commodity in self._current_terminal_commodities:
                raise NotImplementedError()  # TODO - Transform each commodity into a Commodity object
                raise NotImplementedError()  # TODO - Sort commodities by "type"
                raise NotImplementedError()  # TODO - Add each commodities to the table
            logging.info("Commodities loaded successfully for terminal ID : %s", terminal_id)
        except Exception as e:
            logging.error("Failed to load commodities: %s", e)
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            self.main_widget.show_messagebox(await translate("error_error"),
                                             await translate("error_failed_to_load_commodities") + ": " + str(e),
                                             QMessageBox.Icon.Critical)

    def ask_submit(self):
        raise NotImplementedError()  # TODO - Get data to submit from the table and store as temporary list
        raise NotImplementedError()  # TODO - Open a Dialog to Confirm addition of the commodities (#b/#s commodities to send)

    def submit_commodities(self):
        raise NotImplementedError()  # TODO - Submit the commodities stored as temporary list

    def set_gui_enabled(self, enabled):
        for lineedit in self.findChildren(QLineEdit):
            lineedit.setEnabled(enabled)
        for combo in self.findChildren(QComboBox):
            combo.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)
