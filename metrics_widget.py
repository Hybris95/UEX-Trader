# metrics_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
import sqlite3


class MetricsTab(QWidget):
    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(3)
        self.metrics_table.setHorizontalHeaderLabels(["Function", "Execution Time (s)", "Timestamp"])
        layout.addWidget(QLabel("Function Execution Metrics"))
        layout.addWidget(self.metrics_table)

        self.api_calls_table = QTableWidget()
        self.api_calls_table.setColumnCount(5)
        self.api_calls_table.setHorizontalHeaderLabels(["Endpoint", "Call Count", "Cache Hit", "Cache Miss", "Timestamp"])
        layout.addWidget(QLabel("API Call Metrics"))
        layout.addWidget(self.api_calls_table)

        self.load_metrics()

    def load_metrics(self):
        conn = sqlite3.connect('metrics.db')
        c = conn.cursor()

        c.execute("SELECT name, execution_time, timestamp FROM metrics")
        metrics = c.fetchall()
        self.metrics_table.setRowCount(len(metrics))
        for i, (name, execution_time, timestamp) in enumerate(metrics):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
            self.metrics_table.setItem(i, 1, QTableWidgetItem(str(execution_time)))
            self.metrics_table.setItem(i, 2, QTableWidgetItem(timestamp))

        c.execute("SELECT endpoint, call_count, cache_hit, cache_miss, timestamp FROM api_calls")
        api_calls = c.fetchall()
        self.api_calls_table.setRowCount(len(api_calls))
        for i, (endpoint, call_count, cache_hit, cache_miss, timestamp) in enumerate(api_calls):
            self.api_calls_table.setItem(i, 0, QTableWidgetItem(endpoint))
            self.api_calls_table.setItem(i, 1, QTableWidgetItem(str(call_count)))
            self.api_calls_table.setItem(i, 2, QTableWidgetItem(str(cache_hit)))
            self.api_calls_table.setItem(i, 3, QTableWidgetItem(str(cache_miss)))
            self.api_calls_table.setItem(i, 4, QTableWidgetItem(timestamp))

        conn.close()

    def set_gui_enabled(self, enabled):
        return
