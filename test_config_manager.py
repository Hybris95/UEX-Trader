# test_config_manager.py
import pytest
from config_manager import ConfigManager


@pytest.fixture
def config_file(tmpdir):
    config_path = tmpdir.join("config.ini")
    with open(config_path, "w") as f:
        f.write("[API]\nkey=\nsecret_key=\n[SETTINGS]\nis_production=False\n\
                debug=False\nappearance_mode=Light\n[GUI]\nwindow_width=800\nwindow_height=600\n")
    return config_path


@pytest.fixture
def config_manager(config_file):
    return ConfigManager(config_file)


def test_get_api_key(config_manager):
    config_manager.set_api_key("test_key")
    assert config_manager.get_api_key() == "test_key"


def test_get_secret_key(config_manager):
    config_manager.set_secret_key("test_secret_key")
    assert config_manager.get_secret_key() == "test_secret_key"


def test_get_is_production(config_manager):
    config_manager.set_is_production(True)
    assert config_manager.get_is_production() is True


def test_get_debug(config_manager):
    config_manager.set_debug(True)
    assert config_manager.get_debug() is True


def test_get_appearance_mode(config_manager):
    config_manager.set_appearance_mode("Dark")
    assert config_manager.get_appearance_mode() == "Dark"


def test_get_window_size(config_manager):
    config_manager.set_window_size(1024, 768)
    assert config_manager.get_window_size() == (1024, 768)
