# metrics.py
import time
import sqlite3
from functools import wraps
from platformdirs import user_data_dir
from global_variables import app_name, metrics_db_file
import os
import asyncio
from global_variables import metrics_collect_activated
from qasync import QEventLoop


class Metrics:
    _instance = None
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Metrics, cls).__new__(cls)
        return cls._instance

    @staticmethod
    async def get_instance():
        metrics = None
        if Metrics._instance is None:
            metrics = Metrics()
            await metrics.initialize()
        else:
            metrics = Metrics._instance
        return metrics

    def __init__(self):
        if not hasattr(self, 'singleton'):  # Ensure __init__ is only called once
            # Initialize SQLite database
            db_dir = user_data_dir(app_name, ensure_exists=True)
            db_path = os.path.join(db_dir, metrics_db_file)
            self.conn = sqlite3.connect(db_path, isolation_level=None)  # Use autocommit mode
            self.c = self.conn.cursor()
            self.c.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode
            # Set synchronous mode to NORMAL for a balance between performance and integrity
            self.c.execute('PRAGMA synchronous=NORMAL')
            self.c.execute('''CREATE TABLE IF NOT EXISTS fnc_exec
                             (module_name TEXT, function_name TEXT, execution_time REAL,
                              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            self.c.execute('''CREATE TABLE IF NOT EXISTS api_calls
                             (endpoint TEXT, params TEXT, cache_hit INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            self.conn.commit()
            self.fnc_exec_buffer = []
            self.api_calls_buffer = []
            self.batch_size = 1000  # Number of records to batch insert
            self.batch_interval = 5  # Time interval in seconds to perform batch insert
            self.singleton = True
            if metrics_collect_activated:
                loop = QEventLoop()
                asyncio.set_event_loop(loop)
                loop.create_task(self.batch_insert_task())

    async def initialize(self):
        async with self._lock:
            if not self._initialized.is_set():
                self._initialized.set()

    async def batch_insert_task(self):
        while metrics_collect_activated:
            await asyncio.sleep(self.batch_interval)
            await self.perform_batch_insert()

    async def perform_batch_insert(self):
        async with self._lock:
            if metrics_collect_activated:
                if self.fnc_exec_buffer:
                    self.c.executemany("INSERT INTO fnc_exec (module_name, function_name, execution_time) VALUES (?, ?, ?)",
                                       self.fnc_exec_buffer)
                    self.fnc_exec_buffer.clear()
                if self.api_calls_buffer:
                    self.c.executemany("INSERT INTO api_calls (endpoint, params, cache_hit) VALUES (?, ?, ?)",
                                       self.api_calls_buffer)
                    self.api_calls_buffer.clear()
                self.conn.commit()

    @staticmethod
    def track_sync_fnc_exec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            instance = Metrics._instance or Metrics()
            start_time = time.time()
            result = func(*args, **kwargs)
            if metrics_collect_activated:
                end_time = time.time()
                execution_time = end_time - start_time
                instance.fnc_exec_buffer.append((func.__module__, func.__name__, execution_time))
                if len(instance.fnc_exec_buffer) >= instance.batch_size:
                    asyncio.create_task(instance.perform_batch_insert())
            return result
        return wrapper

    @staticmethod
    def track_async_fnc_exec(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            instance = await Metrics.get_instance()
            start_time = time.time()
            result = await func(*args, **kwargs)
            if metrics_collect_activated:
                end_time = time.time()
                execution_time = end_time - start_time
                instance.fnc_exec_buffer.append((func.__module__, func.__name__, execution_time))
                if len(instance.fnc_exec_buffer) >= instance.batch_size:
                    await instance.perform_batch_insert()
            return result
        return wrapper

    @track_sync_fnc_exec
    def track_api_call(self, endpoint: str, params: dict, cache_hit: bool):
        if metrics_collect_activated:
            self.api_calls_buffer.append((endpoint, str(params), 1 if cache_hit else 0))
            if len(self.api_calls_buffer) >= self.batch_size:
                asyncio.create_task(self.perform_batch_insert())

    @track_sync_fnc_exec
    def fetch_fnc_exec(self):
        self.c.execute('''SELECT module_name, function_name, COUNT(1) as nb_exec,
                          AVG(execution_time) as mean_exec_time,
                          MAX(execution_time) as max_exec_time,
                          MIN(execution_time) as min_exec_time,
                          SUM(execution_time) as total_time
                          FROM fnc_exec
                          GROUP BY module_name, function_name
                          ORDER BY total_time DESC''')
        return self.c.fetchall()

    @track_sync_fnc_exec
    def fetch_api_calls(self):
        self.c.execute('''SELECT endpoint, COUNT(1) as nb_calls,
                          SUM(cache_hit) as cache_hit
                          FROM api_calls
                          GROUP BY endpoint
                          ORDER BY nb_calls DESC''')
        return self.c.fetchall()

    @track_sync_fnc_exec
    def remove_all_metrics(self):
        self.c.execute('DELETE FROM api_calls')
        self.c.execute('DELETE FROM fnc_exec')
        self.conn.commit()

    async def close(self):
        await self.perform_batch_insert()  # Ensure all buffered data is written before closing
        self.conn.close()
