# translation_manager.py
import configparser
import asyncio


class TranslationManager:
    _instance = None
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(TranslationManager, cls).__new__(cls)
        return cls._instance

    @staticmethod
    async def get_instance(translation_file="_internal/translations.ini"):
        manager = None
        if TranslationManager._instance is None:
            manager = TranslationManager(translation_file)
            await manager.initialize()
        else:
            manager = TranslationManager._instance
        return manager

    def __init__(self, translation_file="_internal/translations.ini"):
        if not hasattr(self, 'singleton'):  # Ensure __init__ is only called once
            self.translation_file = translation_file
            self.translation_config = configparser.ConfigParser()
            self.load_translations()
            self.available_langs = [
                "en",
                "fr",
                "ru"
            ]
            self.singleton = True

    async def initialize(self):
        async with self._lock:
            # Make sure any resource to be initialized is initialized here
            self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    def load_translations(self):
        self.translation_config.read(self.translation_file, encoding="UTF-8")

    def get_available_lang(self):
        return self.available_langs

    def get_lang_name(self, lang):
        for item in self.available_langs:
            if lang is item or lang == item:
                return self.get_translation("current_language", lang)
        return "Unknown"

    # Use "ISO 639 language codes" as lang
    def get_translation(self, key, lang="en"):
        for item in self.available_langs:
            if lang is item or lang == item:
                value = self.translation_config.get(lang, key, fallback=key)
                if value == key:
                    return self.translation_config.get("en", key, fallback=key)
                return value
        return self.translation_config.get("en", key, fallback=key)
