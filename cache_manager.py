# cache_manager.py
from atexit import register
import json
import os
import sqlite3
import time

from datetime import datetime, timedelta
from platformdirs import user_data_dir
from global_variables import app_name, cache_db_file
from metrics import Metrics


class DictCacheBackend:
    """
    A simple dictionary-based cache backend with time-to-live (TTL) support.

    Everything is stored in memory, so this cache is not suitable for large
    amounts of data, but it's useful for development purposes.

    This cache backend acts as a wrapper around the built-in dict type.
    >>> cache = DictCacheBackend()
    >>> cache['foo'] = 'bar'
    >>> cache['foo']
    bar

    But it also supports time-to-live (TTL) for cache entries.

    >>> cache = DictCacheBackend(ttl=3)
    >>> cache['foo'] = 'bar'
    >>> cache['foo']
    bar
    >>> time.sleep(5)
    >>> cache['foo']
    None

    Properties:
        ttl (int): The time-to-live for cache entries in seconds.

    Methods:
        clear():
            Clears all entries in the cache.
    """
    def __init__(self):
        self.__cache = {}

    def clear(self):
        self.__cache.clear()

    def clean_obsolete(self, ttl: int):
        obsolete_ts = time.time() - ttl
        to_remove = []
        for key in self.__cache:
            value = self.__cache[key]
            if value['timestamp'] < obsolete_ts:
                to_remove.append(key)
        for remove_key in to_remove:
            del self.__cache[remove_key]

    def __getitem__(self, key):
        return self.__cache.get(key, None)

    def __setitem__(self, key, value):
        self.__cache[key] = {
            'data': value,
            'timestamp': time.time()
        }

    def __delitem__(self, key):
        del self.__cache[key]

    def __contains__(self, key):
        return key in self.__cache


class SQLiteCacheBackend:
    """
    A SQLite-based cache backend with time-to-live (TTL) support.
    """

    def __init__(self, in_memory=False):
        if in_memory is True:
            self.db_path = ":memory:"
        else:
            db_dir = user_data_dir(app_name, ensure_exists=True)
            self.db_path = os.path.join(db_dir, cache_db_file)

        self.con = sqlite3.connect(self.db_path)
        self.__create_table()
        register(self.con.close)

    def __create_table(self):
        cur = self.con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp TEXT
            )
        """)
        self.con.commit()
        cur.close()

    def clear(self):
        cur = self.con.cursor()
        cur.execute("DELETE FROM cache;")
        self.con.commit()
        cur.close()

    def clean_obsolete(self, ttl: int):
        # Calculate the threshold timestamp
        threshold_time = datetime.now() - timedelta(seconds=ttl)
        threshold_time_iso = threshold_time.isoformat()

        # Execute the DELETE statement
        cur = self.con.cursor()
        cur.execute("""
            DELETE FROM cache
            WHERE timestamp < ?;
        """, [threshold_time_iso])
        self.con.commit()
        cur.close()

    def __getitem__(self, key):
        cur = self.con.cursor()
        res = cur.execute("""
            SELECT value, timestamp
                FROM cache
                WHERE key = ?;
        """, [key]).fetchone()
        cur.close()

        if res is None:
            return None

        return {
            "data": json.loads(res[0]),
            "timestamp": datetime.fromisoformat(res[1]).timestamp()
        }

    def __setitem__(self, key, value):
        cur = self.con.cursor()
        cur.execute("""
            INSERT INTO cache
            VALUES (:key, :value, :ts)
            ON CONFLICT(key) DO UPDATE SET value = :value, timestamp = :ts;
        """, {
            "key": key,
            "value": json.dumps(value),
            "ts": datetime.now().isoformat()
        })
        self.con.commit()
        cur.close()

    def __delitem__(self, key):
        cur = self.con.cursor()
        cur.execute("DELETE FROM cache WHERE key = ?;", [key])
        self.con.commit()
        cur.close()

    def __contains__(self, key):
        return self.__getitem__(key) is not None


class CacheManager:
    def __init__(self, backend="persistent"):
        if backend == "persistent":
            self.cache = SQLiteCacheBackend()
        elif backend == "local":
            self.cache = DictCacheBackend()
        else:
            raise ValueError("Invalid cache backend: {}".format(backend))

    @Metrics.track_sync_fnc_exec
    def get(self, key: str, ttl: int):
        data = None
        if key in self.cache:
            entry = self.cache[key]
            if ((time.time() - entry['timestamp']) < ttl):
                data = entry['data']
            else:
                del self.cache[key]
        return data

    @Metrics.track_sync_fnc_exec
    def set(self, key, data=[]):
        self.cache[key] = data

    @Metrics.track_sync_fnc_exec
    def replace(self, key: str, new_data, ttl: int, primary_key=['id']):
        old_data = self.get(key, ttl)
        if not old_data:
            return
        if isinstance(old_data, list):
            new_list = []
            list_modified = False
            for old_value in old_data:
                for new_value in new_data:
                    existing_value = True
                    for key in primary_key:
                        if old_value[key] != new_value[key]:
                            existing_value = False
                    if existing_value:
                        new_list.append(new_value)
                        list_modified = True
                    else:
                        new_list.append(old_value)
            if list_modified:
                self.cache[key] = new_list  # TODO - Make sure timestamp is not modified !
        if isinstance(old_data, dict):
            return  # TODO - Replace with dictionary ?

    @Metrics.track_sync_fnc_exec
    def invalidate(self, key):
        if key in self.cache:
            del self.cache[key]

    @Metrics.track_sync_fnc_exec
    def clean_obsolete(self, ttl: int):
        self.cache.clean_obsolete(ttl)

    @Metrics.track_sync_fnc_exec
    def clear(self):
        self.cache.clear()
