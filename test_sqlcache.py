from cache_manager import CacheManager
# from global_variables import persistent_cache_activated # TODO - Add functional test with persistence activated/deactivated


# Unitary tests
def test_unitary_set_and_get():
    sqlcache = CacheManager(backend="persistent")
    dictcache = CacheManager(backend="local")
    sqlcache.set('/foo', 'foo', 'bar')
    dictcache.set('/foo', 'foo', 'bar')
    assert sqlcache.get('/foo', 'foo') == 'bar'
    assert dictcache.get('/foo', 'foo') == 'bar'


# # Can't test the timeout 1 anymore since TTL are calculated from endpoints
# # (we would have to wait 1800s unless we modify default_ttl...)
# def test_unitary_expired_key():
#     sqlcache = CacheManager(backend="persistent")
#     dictcache = CacheManager(backend="local")
#     sqlcache.set('/foo', 'foo', 'bar')
#     dictcache.set('/foo', 'foo', 'bar')
#     time.sleep(1)
#     assert sqlcache.get('/foo', 'foo') is None
#     assert dictcache.get('/foo', 'foo') is None


def test_unitary_clear():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('/foo', 'foo', 'bar')
    sqlcache.clear()
    assert sqlcache.get('/foo', 'foo') is None


def test_unitary_invalidated_key():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set('/foo', 'foo', 'bar')
    sqlcache.set('/foo', 'baz', 'qux')
    sqlcache.invalidate('/foo', 'foo')
    assert sqlcache.get('/foo', 'foo') is None
    assert sqlcache.get('/foo', 'baz') == 'qux'


def test_unitary_endpoint_exists():
    sqlcache = CacheManager(backend="persistent")
    sqlcache.set("/foo", 'foo', 'bar')
    assert sqlcache.endpoint_exists_in_cache("/foo")
    assert not sqlcache.endpoint_exists_in_cache("/bar")


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
    sqlcache1.set('/foo', 'foo', 'bar')
    dictcache1.set('/foo', 'foo', 'bar')
    assert sqlcache1.get('/foo', 'foo') == 'bar'
    assert dictcache1.get('/foo', 'foo') == 'bar'
    sqlcache2 = CacheManager(backend="persistent")
    dictcache2 = CacheManager(backend="local")
    assert sqlcache2.get('/foo', 'foo') == 'bar'
    assert dictcache2.get('/foo', 'foo') is None


# Functional tests
# @pytest.mark.asyncio
# async def test_functional_get_clear(trader):
#     versions = await trader.api.fetch_versions()
#     assert trader.api.cache.get('/game_versions', {}) == versions
#     trader.config_tab.clear_cache()
#     assert trader.api.cache.get('/game_versions', {}) is None
