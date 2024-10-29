# config_manager.py
import configparser
import logging
import base64

logger = logging.getLogger(__name__)


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
        encoded_key = self.config.get("API", "key", fallback="")
        return base64.b64decode(encoded_key).decode('utf-8') if encoded_key else ""

    def set_api_key(self, key):
        if "API" not in self.config:
            self.config["API"] = {}
        encoded_key = base64.b64encode(key.encode('utf-8')).decode('utf-8')
        self.config['API']['key'] = encoded_key
        self.save_config()

    def get_secret_key(self):
        encoded_secret_key = self.config.get("API", "secret_key", fallback="")
        return base64.b64decode(encoded_secret_key).decode('utf-8') if encoded_secret_key else ""

    def set_secret_key(self, secret_key):
        if "API" not in self.config:
            self.config["API"] = {}
        encoded_secret_key = base64.b64encode(secret_key.encode('utf-8')).decode('utf-8')
        self.config['API']['secret_key'] = encoded_secret_key
        self.save_config()

    def get_is_production(self):
        return self.config.getboolean("SETTINGS", "is_production", fallback=False)

    def set_is_production(self, is_production):
        if "SETTINGS" not in self.config:
            self.config["SETTINGS"] = {}
        self.config["SETTINGS"]["is_production"] = str(is_production)
        self.save_config()

    def get_debug(self):
        return self.config.getboolean("SETTINGS", "debug", fallback=False)

    def set_debug(self, debug):
        if "SETTINGS" not in self.config:
            self.config["SETTINGS"] = {}
        self.config["SETTINGS"]["debug"] = str(debug)
        self.save_config()

    def get_appearance_mode(self):
        return self.config.get("SETTINGS", "appearance_mode", fallback="Light")

    def set_appearance_mode(self, mode):
        if "SETTINGS" not in self.config:
            self.config["SETTINGS"] = {}
        self.config["SETTINGS"]["appearance_mode"] = mode
        self.save_config()

    def set_window_size(self, width, height):
        if "GUI" not in self.config:
            self.config["GUI"] = {}
        self.config["GUI"]["window_width"] = str(width)
        self.config["GUI"]["window_height"] = str(height)
        self.save_config()

    def get_window_size(self):
        width = int(self.config.get("GUI", "window_width", fallback="800"))
        height = int(self.config.get("GUI", "window_height", fallback="600"))
        return width, height
