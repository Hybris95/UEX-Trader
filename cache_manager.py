# cache_manager.py
from atexit import register
import json
import os
import sqlite3
import time

from datetime import datetime, timedelta
from platformdirs import user_config_dir

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

    def __getitem__(self, key):
        return self.__cache.get(key, None)

    def __setitem__(self, name, value):
        self.__cache[name] = {
            'data': value,
            'timestamp': time.time()
        }

    def __delitem__(self, name):
        del self.__cache[name]

    def __contains__(self, name):
        return name in self.__cache


class SQLiteCacheBackend:
    """
    A SQLite-based cache backend with time-to-live (TTL) support.
    """

    def __init__(self, in_memory = False):
        if in_memory is True:
            self.db_path = ":memory:"
        else:
            db_dir = user_config_dir("uex_trader", ensure_exists=True)
            self.db_path = os.path.join(db_dir, "cache.db")

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


    def __getitem__(self, key):
        cur = self.con.cursor()
        res = cur.execute("""
            SELECT value, timestamp
                FROM cache 
                WHERE key = ?;
        """, (key, datetime.now().isoformat())).fetchone()
        cur.close()        

        if res is None:
            return None
        
        return {
            "data": json.loads(res[0]),
            "timestamp": datetime.fromisoformat(res[1])
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
        cur.execute("DELETE FROM cache WHERE key = ?;", key)
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

    def get(self, key, ttl):
        data = None
        if key in self.cache:
            entry = self.cache[key]
            if ((time.time() - entry['timestamp']) < ttl):
                data = entry['data']
            else:
                del self.cache[key]
        return data

    def set(self, key, data):
        self.cache[key] = data

    def invalidate(self, key):
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        self.cache.clear()
