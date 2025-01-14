from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton
from metrics import Metrics
from tools import create_async_callback
import asyncio


class MetricsTab(QWidget):
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.metrics = None
        asyncio.ensure_future(self.load_metrics())

    async def initialize(self):
        async with self._lock:
            if not self._initialized.is_set():
                self.metrics = await Metrics.get_instance()
                self.init_ui()
                self._initialized.set()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.fnc_exec_table = QTableWidget()
        self.fnc_exec_table.setColumnCount(7)
        self.fnc_exec_table.setHorizontalHeaderLabels(["Module", "Function", "Exec Count",
                                                       "Mean Time (ms)", "Max Time (ms)",
                                                       "Min Time (ms)", "Total Time (ms)"])
        layout.addWidget(QLabel("Function Execution Metrics"))
        layout.addWidget(self.fnc_exec_table)

        self.api_calls_table = QTableWidget()
        self.api_calls_table.setColumnCount(3)
        self.api_calls_table.setHorizontalHeaderLabels(["Endpoint", "Call Count", "Cache Hit Ratio"])
        layout.addWidget(QLabel("API Call Metrics"))
        layout.addWidget(self.api_calls_table)

        self.refresh_button = QPushButton("Refresh Metrics")
        self.refresh_button.clicked.connect(create_async_callback(self.refresh_metrics))
        layout.addWidget(self.refresh_button)

        self.clear_metrics_button = QPushButton("Erase Metrics")
        self.clear_metrics_button.clicked.connect(create_async_callback(self.erase_metrics))
        layout.addWidget(self.clear_metrics_button)

    async def refresh_metrics(self):
        self.clear_metrics()
        await self.load_metrics()

    async def erase_metrics(self):
        await self.ensure_initialized()
        self.clear_metrics()
        self.metrics.remove_all_metrics()

    def clear_metrics(self):
        self.fnc_exec_table.clear()
        self.api_calls_table.clear()

    async def load_metrics(self):
        await self.ensure_initialized()
        fnc_exec = self.metrics.fetch_fnc_exec()
        self.fnc_exec_table.setRowCount(len(fnc_exec))
        for i, (module_name, function_name,
                nb_exec, mean_exec_time,
                max_exec_time, min_exec_time,
                total_time) in enumerate(fnc_exec):
            self.fnc_exec_table.setItem(i, 0, QTableWidgetItem(module_name))
            self.fnc_exec_table.setItem(i, 1, QTableWidgetItem(function_name))
            self.fnc_exec_table.setItem(i, 2, QTableWidgetItem(f"{str(nb_exec)}"))
            self.fnc_exec_table.setItem(i, 3, QTableWidgetItem(f"{round(mean_exec_time*1000,0)}ms"))
            self.fnc_exec_table.setItem(i, 4, QTableWidgetItem(f"{round(max_exec_time*1000,0)}ms"))
            self.fnc_exec_table.setItem(i, 5, QTableWidgetItem(f"{round(min_exec_time*1000,0)}ms"))
            self.fnc_exec_table.setItem(i, 6, QTableWidgetItem(f"{round(total_time, 0)}ms"))

        api_calls = self.metrics.fetch_api_calls()
        self.api_calls_table.setRowCount(len(api_calls))
        for i, (endpoint, nb_calls, cache_hit) in enumerate(api_calls):
            self.api_calls_table.setItem(i, 0, QTableWidgetItem(endpoint))
            self.api_calls_table.setItem(i, 1, QTableWidgetItem(str(nb_calls)))
            self.api_calls_table.setItem(i, 2, QTableWidgetItem(f"{(cache_hit/nb_calls)*100:.2f}%"))

    def set_gui_enabled(self, enabled):
        return
