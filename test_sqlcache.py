import time

from cache_manager import CacheManager


def test_set_and_get():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('foo', 'bar')

    assert sqlcache.get('foo', 1800) == 'bar'


def test_set_and_returns_none_on_expiration():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('foo', 'bar')

    time.sleep(1)

    assert sqlcache.get('foo', 1) is None


def test_clear():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('foo', 'bar')
    sqlcache.clear()

    assert sqlcache.get('foo', 1) is None


def test_delete_key():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('foo', 'bar')
    sqlcache.set('baz', 'qux')
    sqlcache.invalidate('foo')

    assert sqlcache.get('foo', 1) is None
    assert sqlcache.get('baz', 10) == 'qux'
