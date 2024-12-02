# test_api_manager.py
import pytest
import aiohttp


@pytest.mark.asyncio
async def test_wrong_endpoints(trader):
    api_manager = trader.api
    try:
        await api_manager.fetch_data("/unknown_endpoint")
        assert False
    except aiohttp.ClientError as e:
        assert str(e).startswith("404")
    try:
        await api_manager.fetch_data("malformed_endpoint")
        assert False
    except aiohttp.ClientError as e:
        assert str(e).startswith("404")


@pytest.mark.asyncio
async def test_manual_fetch_data(trader):
    api_manager = trader.api
    response = await api_manager.fetch_data("/factions")
    assert len(response.get("data", [])) != 0
    response = await api_manager.fetch_data("/companies", "is_vehicle_manufacturer=1")
    assert len(response.get("data", [])) != 0


# @pytest.mark.asyncio
# async def test_post_data_no_keys(trader):
#     api_manager = trader.api


# @pytest.mark.asyncio
# async def test_fetch_commodity(trader):
#     api_manager = trader.api


# @pytest.mark.asyncio
# async def test_fetch_terminal(trader):
#     api_manager = trader.api


# @pytest.mark.asyncio
# async def test_fetch_planet(trader):
#     api_manager = trader.api


# @pytest.mark.asyncio
# async def test_fetch_system(trader):
#     api_manager = trader.api


# @pytest.mark.asyncio
# async def test_fetch_route(trader):
#     api_manager = trader.api
