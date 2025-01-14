# metrics.py
import time
import sqlite3
from functools import wraps
from platformdirs import user_data_dir
from global_variables import app_name, metrics_db_file
import os
import asyncio
from global_variables import metrics_collect_activated


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
            self.conn = sqlite3.connect(db_path)
            self.c = self.conn.cursor()
            self.c.execute('''CREATE TABLE IF NOT EXISTS fnc_exec
                             (module_name TEXT, function_name TEXT, execution_time REAL,
                              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            self.c.execute('''CREATE TABLE IF NOT EXISTS api_calls
                             (endpoint TEXT, params TEXT, cache_hit INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            self.conn.commit()
            self.singleton = True

    async def initialize(self):
        async with self._lock:
            if not self._initialized.is_set():
                self._initialized.set()

    @classmethod
    def track_sync_fnc_exec(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            instance = cls._instance or cls()
            start_time = time.time()
            result = func(*args, **kwargs)
            if metrics_collect_activated:
                end_time = time.time()
                execution_time = end_time - start_time
                instance.c.execute("INSERT INTO fnc_exec (module_name, function_name, execution_time) VALUES (?, ?, ?)",
                                   (func.__module__, func.__name__, execution_time))
                instance.conn.commit()
            return result
        return wrapper

    @classmethod
    def track_async_fnc_exec(cls, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            instance = await cls.get_instance()
            start_time = time.time()
            result = await func(*args, **kwargs)
            if metrics_collect_activated:
                end_time = time.time()
                execution_time = end_time - start_time
                instance.c.execute("INSERT INTO fnc_exec (module_name, function_name, execution_time) VALUES (?, ?, ?)",
                                   (func.__module__, func.__name__, execution_time))
                instance.conn.commit()
            return result
        return wrapper

    def track_api_call(self, endpoint: str, params: dict, cache_hit: bool):
        if metrics_collect_activated:
            self.c.execute("INSERT INTO api_calls (endpoint, params, cache_hit) VALUES (?, ?, ?)",
                           (endpoint, str(params), 1 if cache_hit else 0))
            self.conn.commit()

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

    def fetch_api_calls(self):
        self.c.execute('''SELECT endpoint, COUNT(1) as nb_calls,
                          SUM(cache_hit) as cache_hit
                          FROM api_calls
                          GROUP BY endpoint
                          ORDER BY nb_calls DESC''')
        return self.c.fetchall()

    def remove_all_metrics(self):
        self.c.execute('DELETE FROM api_calls')
        self.c.execute('DELETE FROM fnc_exec')
        self.conn.commit()

    def close(self):
        self.conn.close()
