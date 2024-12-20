# test_api_manager.py
import pytest
import aiohttp


@pytest.mark.asyncio
async def test_wrong_endpoints(api):
    try:
        try:
            await api._fetch_data("/unknown_endpoint")
            assert False
        except aiohttp.ClientError as e:
            assert str(e).startswith("404")
        try:
            await api._fetch_data("malformed_endpoint")
            assert False
        except aiohttp.ClientError as e:
            assert str(e).startswith("404")
    except Exception:
        assert False


@pytest.mark.asyncio
async def test_manual_fetch_data(api):
    assert len((await api._fetch_data("/factions")).get("data", [])) != 0
    assert len((await api._fetch_data("/companies", {"is_vehicle_manufacturer":1})).get("data", [])) != 0


# @pytest.mark.asyncio
# async def test_post_data_no_keys(api):


# @pytest.mark.asyncio
# async def test_fetch_commodity(api):


# @pytest.mark.asyncio
# async def test_fetch_terminal(api):


# @pytest.mark.asyncio
# async def test_fetch_planet(api):


# @pytest.mark.asyncio
# async def test_fetch_system(api):


# @pytest.mark.asyncio
# async def test_fetch_route(api):
