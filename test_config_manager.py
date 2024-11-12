# test_config_manager.py
import pytest
from config_manager import ConfigManager


@pytest.fixture
def config_file(tmpdir):
    config_path = tmpdir.join("config.ini")
    with open(config_path, "w") as f:
        f.writelines(["[API]", "key=c3RvcmVkS2V5", "secret_key=c3RvcmVkU2VjcmV0S2V5"])
        f.writelines(["[SETTINGS]", "is_production=False", "debug=True", "appearance_mode=Light"])
        f.writelines(["[GUI]", "window_width=1024", "window_height=768"])
    return config_path


@pytest.fixture
def config_manager(config_file):
    if ConfigManager._instance is None:
        return ConfigManager(config_file)
    else:
        return ConfigManager._instance


def test_get_api_key(config_manager):
    assert config_manager.get_api_key() == "storedKey"
    config_manager.set_api_key("test_key")
    assert config_manager.get_api_key() == "test_key"


def test_get_secret_key(config_manager):
    assert config_manager.get_secret_key() == "storedSecretKey"
    config_manager.set_secret_key("test_secret_key")
    assert config_manager.get_secret_key() == "test_secret_key"


def test_get_is_production(config_manager):
    assert config_manager.get_is_production() is False
    config_manager.set_is_production(True)
    assert config_manager.get_is_production() is True
    config_manager.set_is_production(False)
    assert config_manager.get_is_production() is False


def test_get_debug(config_manager):
    assert config_manager.get_debug() is True
    config_manager.set_debug(False)
    assert config_manager.get_debug() is False
    config_manager.set_debug(True)
    assert config_manager.get_debug() is True


def test_get_appearance_mode(config_manager):
    assert config_manager.get_appearance_mode() == "Light"
    config_manager.set_appearance_mode("Dark")
    assert config_manager.get_appearance_mode() == "Dark"
    config_manager.set_appearance_mode("Light")
    assert config_manager.get_appearance_mode() == "Light"


def test_get_window_size(config_manager):
    assert config_manager.get_window_size() == (1024, 768)
    config_manager.set_window_size(800, 600)
    assert config_manager.get_window_size() == (800, 600)
