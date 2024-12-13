# cache_manager.py
import time


class CacheManager:
    def __init__(self, ttl=300):
        self.ttl = ttl  # Time-to-live for cache in seconds
        self.cache = {}

    def get(self, key):
        data = None
        if key in self.cache:
            entry = self.cache[key]
            if ((time.time() - entry['timestamp']) < self.ttl):
                data = entry['data']
            else:
                del self.cache[key]
        return data

    def set(self, key, data):
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }

    def invalidate(self, key):
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        self.cache.clear()
