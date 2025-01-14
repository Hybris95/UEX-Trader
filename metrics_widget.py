from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton
from metrics import Metrics


class MetricsTab(QWidget):
    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.metrics = Metrics()
        self.init_ui()
        self.load_metrics()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.fnc_exec_table = QTableWidget()
        self.fnc_exec_table.setColumnCount(5)
        self.fnc_exec_table.setHorizontalHeaderLabels(["Function", "Exec Count",
                                                       "Mean Time (s)", "Max Time (s)", "Min Time (s)"])
        layout.addWidget(QLabel("Function Execution Metrics"))
        layout.addWidget(self.fnc_exec_table)

        self.api_calls_table = QTableWidget()
        self.api_calls_table.setColumnCount(3)
        self.api_calls_table.setHorizontalHeaderLabels(["Endpoint", "Call Count", "Cache Hit Ratio"])
        layout.addWidget(QLabel("API Call Metrics"))
        layout.addWidget(self.api_calls_table)

        self.refresh_button = QPushButton("Refresh Metrics")
        self.refresh_button.clicked.connect(self.refresh_metrics)
        layout.addWidget(self.refresh_button)

    def refresh_metrics(self):
        self.clear_metrics()
        self.load_metrics()

    def clear_metrics(self):
        self.fnc_exec_table.clear()
        self.api_calls_table.clear()

    def load_metrics(self):
        fnc_exec = self.metrics.fetch_fnc_exec()
        self.fnc_exec_table.setRowCount(len(fnc_exec))
        for i, (function_name, nb_exec, mean_exec_time, max_exec_time, min_exec_time) in enumerate(fnc_exec):
            self.fnc_exec_table.setItem(i, 0, QTableWidgetItem(function_name))
            self.fnc_exec_table.setItem(i, 1, QTableWidgetItem(f"{str(nb_exec)}"))
            self.fnc_exec_table.setItem(i, 2, QTableWidgetItem(f"{mean_exec_time*1000:d}ms"))
            self.fnc_exec_table.setItem(i, 3, QTableWidgetItem(f"{max_exec_time*1000:d}ms"))
            self.fnc_exec_table.setItem(i, 4, QTableWidgetItem(f"{min_exec_time*1000:d}ms"))

        api_calls = self.metrics.fetch_api_calls()
        self.api_calls_table.setRowCount(len(api_calls))
        for i, (endpoint, nb_calls, cache_hit) in enumerate(api_calls):
            self.api_calls_table.setItem(i, 0, QTableWidgetItem(endpoint))
            self.api_calls_table.setItem(i, 1, QTableWidgetItem(str(nb_calls)))
            self.api_calls_table.setItem(i, 2, QTableWidgetItem(f"{(cache_hit/nb_calls)*100:.2f}%"))

    def set_gui_enabled(self, enabled):
        return
