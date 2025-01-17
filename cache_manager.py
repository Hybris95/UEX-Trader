# cache_manager.py
from atexit import register
import json
import os
import sqlite3
import time
import hashlib
import logging

from datetime import datetime, timedelta
from platformdirs import user_data_dir
from global_variables import app_name, cache_db_file
from global_variables import system_ttl, planet_ttl, terminal_ttl, default_ttl
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

    def contains_endpoint(self, endpoint):
        for key in self.__cache:
            key_endpoint = '_'.join(key.split('_')[:-1])
            if key_endpoint == endpoint:
                return True
        return False


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
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp TEXT
                )
            """)
            self.con.commit()
        except sqlite3.OperationalError:
            return  # TODO - Log error instead
        finally:
            cur.close()

    def clear(self):
        cur = self.con.cursor()
        try:
            cur.execute("DELETE FROM cache;")
            self.con.commit()
        except sqlite3.OperationalError:
            return  # TODO - Log error instead
        finally:
            cur.close()

    def clean_obsolete(self, ttl: int):
        # Calculate the threshold timestamp
        threshold_time = datetime.now() - timedelta(seconds=ttl)
        threshold_time_iso = threshold_time.isoformat()

        # Execute the DELETE statement
        cur = self.con.cursor()
        try:
            cur.execute("""
                DELETE FROM cache
                WHERE timestamp < ?;
            """, [threshold_time_iso])
            self.con.commit()
        except sqlite3.OperationalError:
            return  # TODO - Log error instead
        finally:
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
        try:
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
        except sqlite3.OperationalError:
            return  # TODO - Log error instead
        finally:
            cur.close()

    def __delitem__(self, key):
        cur = self.con.cursor()
        try:
            cur.execute("DELETE FROM cache WHERE key = ?;", [key])
            self.con.commit()
        except sqlite3.OperationalError:
            return  # TODO - Log error instead
        finally:
            cur.close()

    def __contains__(self, key):
        return self.__getitem__(key) is not None

    def contains_endpoint(self, endpoint):
        cur = self.con.cursor()
        res = cur.execute("""
            SELECT COUNT(1)
            FROM cache
            WHERE key LIKE CONCAT(?, '\_%') ESCAPE '\\';
        """, [endpoint]).fetchone()
        cur.close()

        if res is None:
            return False
        count = res[0]
        return count > 0


class CacheManager:
    def __init__(self, backend="persistent", config_manager=None):
        if backend == "persistent":
            self.cache = SQLiteCacheBackend()
        elif backend == "local":
            self.cache = DictCacheBackend()
        else:
            raise ValueError("Invalid cache backend: {}".format(backend))
        self.config_manager = config_manager

    @Metrics.track_sync_fnc_exec
    def _get(self, key: str, ttl: int):
        data = None
        logger = self.get_logger()
        if key in self.cache:
            entry = self.cache[key]
            if ((time.time() - entry['timestamp']) < ttl):
                data = entry['data']
                logger.debug(f"Cache hit for {key}")
            else:
                del self.cache[key]
                logger.debug(f"Cache obsolete hit for {key}")
        else:
            logger.debug(f"Cache miss for {key}")
        return data

    @Metrics.track_sync_fnc_exec
    def get(self, endpoint, params):
        key = self._get_key(endpoint, params)
        ttl = self._get_ttl_from_endpoint(endpoint)
        return self._get(key, ttl)

    @Metrics.track_sync_fnc_exec
    def _get_key(self, endpoint, params):
        hashed_params = hashlib.md5(str(params).encode('utf-8')).hexdigest()
        return f"{endpoint}_{hashed_params}"

    @Metrics.track_sync_fnc_exec
    def endpoint_exists_in_cache(self, endpoint):
        return self.cache.contains_endpoint(endpoint)

    @Metrics.track_sync_fnc_exec
    def _set(self, key, data):
        self.cache[key] = data

    @Metrics.track_sync_fnc_exec
    def set(self, endpoint, params, data=[]):
        key = self._get_key(endpoint, params)
        return self._set(key, data)

    @Metrics.track_sync_fnc_exec
    def _replace(self, key: str, new_data, ttl: int, primary_key=['id']):
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
    def _get_ttl_from_endpoint(self, endpoint):
        ttl = default_ttl
        match endpoint:
            case "/star_systems":
                ttl = system_ttl
            case "/planets":
                ttl = planet_ttl
            case "/terminals":
                ttl = terminal_ttl
            case "/commodities_routes":
                ttl = planet_ttl
            case "/game_versions":
                ttl = default_ttl
            case _:
                if self.config_manager:
                    ttl = int(self.config_manager.get_ttl())
        return ttl

    @Metrics.track_sync_fnc_exec
    def replace(self, endpoint, params, new_data, primary_key=['id']):
        key = self._get_key(endpoint, params)
        return self._replace(key, new_data=new_data, ttl=self._get_ttl_from_endpoint(endpoint), primary_key=primary_key)

    @Metrics.track_sync_fnc_exec
    def _invalidate(self, key):
        if key in self.cache:
            del self.cache[key]

    @Metrics.track_sync_fnc_exec
    def invalidate(self, endpoint, params):
        key = self._get_key(endpoint, params)
        self._invalidate(key)

    @Metrics.track_sync_fnc_exec
    def clean_obsolete(self):
        max_ttl = max(system_ttl, planet_ttl, terminal_ttl, default_ttl, int(self.config_manager.get_ttl()))
        self.cache.clean_obsolete(max_ttl)

    @Metrics.track_sync_fnc_exec
    def clear(self):
        self.cache.clear()

    def get_logger(self):
        return logging.getLogger(__name__)
