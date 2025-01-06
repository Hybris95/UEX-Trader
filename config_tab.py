# config_tab.py
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QMessageBox
)
from PyQt5.QtCore import Qt
from config_manager import ConfigManager
from translation_manager import TranslationManager
import asyncio
from tools import translate
from api import API


class ConfigTab(QWidget):
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.config_manager = None
        self.translation_manager = None
        self.main_vboxlayout = None
        self.config_manager = None
        self.translation_manager = None
        self.api = None

    async def initialize(self):
        async with self._lock:
            if self.config_manager is None or self.translation_manager is None or self.main_vboxlayout is None:
                self.config_manager = await ConfigManager.get_instance()
                self.translation_manager = await TranslationManager.get_instance()
                self.api = await API.get_instance(self.config_manager)
                await self.init_ui()
                self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    async def prep_api_key(self):
        # API KEY
        self.api_key_vboxlayout = QVBoxLayout()
        self.api_key_label = QLabel(await translate("config_uexcorp_apikey") + ":")
        self.api_key_link = QLabel()
        self.api_key_link.setOpenExternalLinks(True)
        self.api_key_link.setTextFormat(Qt.TextFormat.RichText)
        self.api_key_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.api_key_link.setText('<a href="https://uexcorp.space/api/apps">' + await translate("api_key_explain") + '</a>')
        self.api_key_input = QLineEdit(self.config_manager.get_api_key())
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.editingFinished.connect(self.update_api_key)
        self.show_api_key_button = QPushButton("👁", self)
        self.show_api_key_button.setFixedSize(30, 30)  # Adjust size as needed
        self.show_api_key_button.pressed.connect(self.show_api_key)
        self.show_api_key_button.released.connect(self.hide_api_key)
        self.api_key_vboxlayout.addWidget(self.api_key_label)
        self.api_key_vboxlayout.addWidget(self.api_key_link)
        self.api_key_vboxlayout.addWidget(self.api_key_input)
        self.api_key_vboxlayout.addWidget(self.show_api_key_button)

    async def prep_secret_key(self):
        # SECRET KEY
        self.secret_key_vboxlayout = QVBoxLayout()
        self.secret_key_label = QLabel(await translate("config_uexcorp_secretkey") + ":")
        self.secret_key_link = QLabel()
        self.secret_key_link.setOpenExternalLinks(True)
        self.secret_key_link.setTextFormat(Qt.TextFormat.RichText)
        self.secret_key_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.secret_key_link.setText('<a href="https://uexcorp.space/account">'
                                     + await translate("access_key_explain") + '</a>')
        self.secret_key_input = QLineEdit(self.config_manager.get_secret_key())
        self.secret_key_input.setEchoMode(QLineEdit.Password)
        self.secret_key_input.editingFinished.connect(self.update_secret_key)
        self.show_secret_key_button = QPushButton("👁", self)
        self.show_secret_key_button.setFixedSize(30, 30)  # Adjust size as needed
        self.show_secret_key_button.pressed.connect(self.show_secret_key)
        self.show_secret_key_button.released.connect(self.hide_secret_key)
        self.secret_key_vboxlayout.addWidget(self.secret_key_label)
        self.secret_key_vboxlayout.addWidget(self.secret_key_link)
        self.secret_key_vboxlayout.addWidget(self.secret_key_input)
        self.secret_key_vboxlayout.addWidget(self.show_secret_key_button)

    async def prep_is_production(self):
        self.is_production_checkbox = QCheckBox(await translate("config_isproduction"))
        self.is_production_checkbox.setChecked(self.config_manager.get_is_production())
        self.is_production_checkbox.stateChanged.connect(self.update_is_production)

    async def prep_debug(self):
        self.debug_checkbox = QCheckBox(await translate("config_debugmode"))
        self.debug_checkbox.setChecked(self.config_manager.get_debug())
        self.debug_checkbox.stateChanged.connect(self.update_debug_mode)

    async def prep_appearance(self):
        self.appearance_label = QLabel(await translate("config_appearancemode") + ":")
        self.appearance_input = QComboBox()
        self.appearance_input.addItem(await translate("appearance_dark"), "Dark")
        self.appearance_input.addItem(await translate("appearance_light"), "Light")
        self.appearance_input.setCurrentIndex(self.appearance_input.findData(self.config_manager.get_appearance_mode()))
        self.appearance_input.currentIndexChanged.connect(self.update_appearance_mode)

    async def prep_language(self):
        self.language_label = QLabel(await translate("config_language") + ":")
        self.language_input = QComboBox()
        langs = self.translation_manager.get_available_lang()
        for lang in langs:
            self.language_input.addItem(self.translation_manager.get_translation("current_language", lang), lang)
        self.language_input.setCurrentIndex(self.language_input.findData(self.config_manager.get_lang()))
        self.language_input.currentIndexChanged.connect(self.update_lang)

    async def prep_version(self):
        self.version_label = QLabel(await translate("config_version") + ":")
        self.version_input = QComboBox()
        versions = await self.api.fetch_versions()
        for version in versions:
            self.version_input.addItem(version + " - " + versions[version], version)
        self.version_input.setCurrentIndex(self.version_input.findData(self.config_manager.get_version()))
        self.version_input.currentIndexChanged.connect(self.update_version)

    async def prep_cache_ttl(self):
        self.cache_ttl_vboxlayout = QVBoxLayout()
        self.cache_ttl_label = QLabel(await translate("config_cache_ttl") + ":")
        self.cache_ttl_input = QLineEdit(self.config_manager.get_ttl())
        self.cache_ttl_input.editingFinished.connect(lambda: asyncio.create_task(self.update_cache_ttl()))
        self.cache_ttl_vboxlayout.addWidget(self.cache_ttl_label)
        self.cache_ttl_vboxlayout.addWidget(self.cache_ttl_input)

    async def populate_main_layout(self):
        self.main_vboxlayout.addLayout(self.api_key_vboxlayout)
        self.main_vboxlayout.addLayout(self.secret_key_vboxlayout)
        self.main_vboxlayout.addWidget(self.is_production_checkbox)
        self.main_vboxlayout.addWidget(self.debug_checkbox)
        self.main_vboxlayout.addWidget(self.appearance_label)
        self.main_vboxlayout.addWidget(self.appearance_input)
        self.main_vboxlayout.addWidget(self.language_label)
        self.main_vboxlayout.addWidget(self.language_input)
        self.main_vboxlayout.addWidget(self.version_label)
        self.main_vboxlayout.addWidget(self.version_input)
        self.main_vboxlayout.addLayout(self.cache_ttl_vboxlayout)

    async def init_ui(self):
        self.main_vboxlayout = QVBoxLayout()
        await self.prep_api_key()
        await self.prep_secret_key()
        await self.prep_is_production()
        await self.prep_debug()
        await self.prep_appearance()
        self.update_appearance_mode()
        await self.prep_language()
        await self.prep_version()
        await self.prep_cache_ttl()
        await self.populate_main_layout()
        self.setLayout(self.main_vboxlayout)

    def show_api_key(self):
        self.api_key_input.setEchoMode(QLineEdit.Normal)

    def hide_api_key(self):
        self.api_key_input.setEchoMode(QLineEdit.Password)

    def show_secret_key(self):
        self.secret_key_input.setEchoMode(QLineEdit.Normal)

    def hide_secret_key(self):
        self.secret_key_input.setEchoMode(QLineEdit.Password)

    def update_appearance_mode(self):
        new_appearance = self.appearance_input.currentData()
        self.config_manager.set_appearance_mode(new_appearance)
        asyncio.ensure_future(self.main_widget.apply_appearance_mode(new_appearance))

    def update_lang(self):
        new_lang = self.language_input.currentData()
        self.config_manager.set_lang(new_lang)
        asyncio.ensure_future(self.main_widget.init_ui())

    def update_version(self):
        new_version = self.version_input.currentData()
        asyncio.ensure_future(self.config_manager.set_version(new_version))

    def update_is_production(self):
        self.config_manager.set_is_production(self.is_production_checkbox.isChecked())

    def update_debug_mode(self):
        self.config_manager.set_debug(self.debug_checkbox.isChecked())

    def update_api_key(self):
        self.config_manager.set_api_key(self.api_key_input.text())

    def update_secret_key(self):
        self.config_manager.set_secret_key(self.secret_key_input.text())

    async def update_cache_ttl(self):
        try:
            self.config_manager.set_ttl(self.cache_ttl_input.text())
        except ValueError as e:
            self.main_widget.show_messagebox(await translate("error_input_error"), str(e), QMessageBox.Icon.Warning)
            self.cache_ttl_input.blockSignals(True)
            self.cache_ttl_input.setText(self.config_manager.get_ttl())
            self.cache_ttl_input.blockSignals(False)

    def set_gui_enabled(self, enabled):
        for lineedit in self.findChildren(QLineEdit):
            lineedit.setEnabled(enabled)
        for combo in self.findChildren(QComboBox):
            combo.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)
        for button in self.findChildren(QCheckBox):
            button.setEnabled(enabled)
