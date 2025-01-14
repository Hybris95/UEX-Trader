# metrics.py
import time
import sqlite3
from functools import wraps
from platformdirs import user_data_dir
from global_variables import app_name, metrics_db_file
import os

# Initialize SQLite database
db_dir = user_data_dir(app_name, ensure_exists=True)
db_path = os.path.join(db_dir, metrics_db_file)
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS metrics
             (name TEXT, execution_time REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS api_calls
             (endpoint TEXT, call_count INTEGER, cache_hit INTEGER, cache_miss INTEGER,
          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()


def track_execution_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        c.execute("INSERT INTO metrics (name, execution_time) VALUES (?, ?)", (func.__name__, execution_time))
        conn.commit()
        return result
    return wrapper


def track_api_calls(endpoint):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_hit = kwargs.pop('cache_hit', False)
            result = await func(*args, **kwargs)
            c.execute("SELECT call_count, cache_hit, cache_miss FROM api_calls WHERE endpoint = ?", (endpoint,))
            row = c.fetchone()
            if row:
                call_count, cache_hit_count, cache_miss_count = row
                call_count += 1
                if cache_hit:
                    cache_hit_count += 1
                else:
                    cache_miss_count += 1
                c.execute("UPDATE api_calls SET call_count = ?, cache_hit = ?, cache_miss = ? WHERE endpoint = ?",
                          (call_count, cache_hit_count, cache_miss_count, endpoint))
            else:
                c.execute("INSERT INTO api_calls (endpoint, call_count, cache_hit, cache_miss) VALUES (?, ?, ?, ?)",
                          (endpoint, 1, 1 if cache_hit else 0, 0 if cache_hit else 1))
            conn.commit()
            return result
        return wrapper
    return decorator
