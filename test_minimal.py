# test_minimal.py
import pytest
from PyQt5.QtWidgets import QApplication, QLabel


@pytest.fixture
def app():
    return QApplication([])


def test_minimal(app):
    label = QLabel("Hello, World!")
    label.show()
    assert label.text() == "Hello, World!"
