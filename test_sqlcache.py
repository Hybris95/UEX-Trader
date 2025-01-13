import time

from cache_manager import CacheManager
# from global_variables import persistent_cache_activated # TODO - Add functional test with persistence activated/deactivated


# Unitary tests
def test_unitary_set_and_get():
    sqlcache = CacheManager(backend="persistent")
    dictcache = CacheManager(backend="local")
    sqlcache.set('foo', 'bar')
    dictcache.set('foo', 'bar')
    assert sqlcache.get('foo', 1800) == 'bar'
    assert dictcache.get('foo', 1800) == 'bar'


def test_unitary_expired_key():
    sqlcache = CacheManager(backend="persistent")
    dictcache = CacheManager(backend="local")
    sqlcache.set('foo', 'bar')
    dictcache.set('foo', 'bar')
    time.sleep(1)
    assert sqlcache.get('foo', 1) is None
    assert dictcache.get('foo', 1) is None


def test_unitary_clear():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('foo', 'bar')
    sqlcache.clear()
    assert sqlcache.get('foo', 1) is None


def test_unitary_invalidated_key():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('foo', 'bar')
    sqlcache.set('baz', 'qux')
    sqlcache.invalidate('foo')
    assert sqlcache.get('foo', 1) is None
    assert sqlcache.get('baz', 10) == 'qux'


def test_unitary_invalid_backend():
    try:
        CacheManager(backend="unknown")
        assert False
    except ValueError:
        assert True
    except Exception:
        assert False


def test_unitary_persistent_key():
    sqlcache1 = CacheManager(backend="persistent")
    dictcache1 = CacheManager(backend="local")
    sqlcache1.set('foo', 'bar')
    dictcache1.set('foo', 'bar')
    assert sqlcache1.get('foo', 1800) == 'bar'
    assert dictcache1.get('foo', 1800) == 'bar'
    sqlcache2 = CacheManager(backend="persistent")
    dictcache2 = CacheManager(backend="local")
    assert sqlcache2.get('foo', 1800) == 'bar'
    assert dictcache2.get('foo', 1800) is None


# Functional tests
# @pytest.mark.asyncio
# async def test_functional_get_clear(trader):
#     versions = await trader.api.fetch_versions()
#     nonehash = '6adf97f83acf6453d4a6a4b1070f3754'
#     assert trader.api.cache.get('/game_versions_' + nonehash, trader.config_manager.get_ttl()) == versions
#     trader.config_tab.clear_cache()
#     assert trader.api.cache.get('/game_versions_' + nonehash, trader.config_manager.get_ttl()) is None
