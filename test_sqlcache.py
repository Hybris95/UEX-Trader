import time
from cache_manager import SQLiteCacheBackend

class TestSqlCache:
    def test_set_and_get(self):
        self.sqlcache = SQLiteCacheBackend(ttl=2, in_memory=True)
        
        self.sqlcache['foo'] = 'bar'
        
        assert self.sqlcache['foo'] == 'bar'


    def test_set_and_returns_none_on_expiration(self):
        self.sqlcache = SQLiteCacheBackend(ttl=1, in_memory=True)
        
        self.sqlcache['foo'] = 'bar'
        time.sleep(2)
        
        assert self.sqlcache['foo'] is None


    def test_clear(self):
        self.sqlcache = SQLiteCacheBackend(ttl=5, in_memory=True)
        
        self.sqlcache['foo'] = 'bar'
        self.sqlcache.clear()
        
        assert self.sqlcache['foo'] is None

    def test_delete_key(self):
        self.sqlcache = SQLiteCacheBackend(ttl=5, in_memory=True)
        
        self.sqlcache['foo'] = 'bar'
        self.sqlcache['baz'] = 'qux'
        
        del self.sqlcache['foo']
        
        assert self.sqlcache['foo'] is None
        assert self.sqlcache['baz'] == 'qux'