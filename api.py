# api.py
import logging
import aiohttp
import json
from cache_manager import CacheManager
import asyncio
import traceback
import hashlib
from itertools import groupby
from operator import itemgetter
from typing import List
from commodity import Commodity


class API:
    _instance = None
    _lock = asyncio.Lock()
    _initialized = asyncio.Event()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(API, cls).__new__(cls)
        return cls._instance

    @staticmethod
    async def get_instance(config_manager):
        api = None
        if API._instance is None:
            api = API(config_manager)
            await api.initialize()
        else:
            api = API._instance
        return api

    def __init__(self, config_manager):
        if not hasattr(self, 'singleton'):  # Ensure __init__ is only called once
            self.config_manager = config_manager
            self.cache = CacheManager()
            self.session = None
            self.singleton = True

    async def initialize(self):
        async with self._lock:
            if self.session is None:
                self.session = aiohttp.ClientSession()
                self._initialized.set()

    async def cleanup(self):
        if self.session:
            await self.session.close()
            self.session = None
        self._initialized.clear()

    async def ensure_initialized(self):
        if not self._initialized.is_set():
            await self.initialize()
        await self._initialized.wait()

    async def __aenter__(self):
        await self.ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_api_base_url(self):
        await self.ensure_initialized()
        if self.config_manager.get_is_production():
            return "https://api.uexcorp.space/2.0"
        return "https://api.uexcorp.space/2.0"

    def get_logger(self):
        return logging.getLogger(__name__)

    async def _fetch_data(self, endpoint, params=None, default_data=[], data_only=True, ttl=None):
        await self.ensure_initialized()
        if not ttl:
            ttl = self.config_manager.get_ttl()
        hashed_params = hashlib.md5(str(params).encode('utf-8')).hexdigest()
        cache_key = f"{endpoint}_{hashed_params}"
        cached_data = self.cache.get(cache_key, int(ttl))
        logger = self.get_logger()
        if cached_data:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_data, True
        else:
            logger.debug(f"Cache miss for {cache_key}")
        url = f"{await self.get_api_base_url()}{endpoint}"
        logger.debug(f"API Request: GET {url} {params if params else ''}")
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    json_response = (await response.json())
                    if data_only:
                        data = json_response.get("data", default_data)
                        self.cache.set(cache_key, data)
                        return data, False
                    else:
                        self.cache.set(cache_key, json_response)
                        return json_response, False
                error_message = await response.text()
                logger.error(f"API request failed with status {response.status}: {error_message}")
                response.raise_for_status()  # Raise an exception for bad status codes
        except aiohttp.ClientResponseError as e:
            logger.error(f"API request failed with status {e.status}: {e.message} - {e.request_info.url}")
            raise  # Re-raise the exception to be handled by the calling function
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            raise  # Re-raise the exception to be handled by the calling function
        except Exception as e:
            logger.error(f"Generic API error: {e}")
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            raise  # Re-raise the exception to be handled by the calling function

    async def _post_data(self, endpoint, data=None):
        await self.ensure_initialized()
        if not data:
            data = {}
        url = f"{await self.get_api_base_url()}{endpoint}"
        logger = self.get_logger()
        # TODO - Check if endpoint is available (list of POST endpoints)
        headers = {
            "Authorization": f"Bearer {self.config_manager.get_api_key()}",  # Send api_key as Bearer Token
            "secret_key": self.config_manager.get_secret_key()
        }
        data['is_production'] = int(self.config_manager.get_is_production())
        data_string = json.dumps(data)
        logger.debug("API Request: POST %s %s", url, data_string)
        try:
            async with self.session.post(url, data=data_string, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    return response_data
                error_message = await response.text()
                logger.error("API request failed with status %s: %s", response.status, error_message)
                response.raise_for_status()  # Raise an exception for bad status codes
        except aiohttp.ClientResponseError as e:
            logger.error("API request failed with status %s: %s - %s", e.status, e.message, e.request_info.url)
            raise  # Re-raise the exception to be handled by the calling function
        except aiohttp.ClientError as e:
            logger.error("API request failed: %s", e)
            raise  # Re-raise the exception to be handled by the calling function
        except Exception as e:
            logger.error(f"Generic API error: {e}")
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())
            raise  # Re-raise the exception to be handled by the calling function

    def _group_by(self, data, param: str):
        logger = self.get_logger()
        try:
            sorted_data_by_param = sorted(data, key=itemgetter(param))
            grouped_data_by_param = [list(group) for _, group in groupby(sorted_data_by_param, key=itemgetter(param))]
            return grouped_data_by_param
        except KeyError as e:
            logger.error(f"API KeyError: {e}")
            if self.config_manager.get_debug():
                logging.debug(traceback.format_exc())

    def _group_by_and_set(self, data, param: str, endpoint: str):
        grouped_data_by_param = self._group_by(data, param)
        for data_grouped in grouped_data_by_param:
            if len(data_grouped) > 0:
                data_grouped_params = {param: data_grouped[0][param]}
                data_grouped_hash = hashlib.md5(str(data_grouped_params).encode('utf-8')).hexdigest()
                self.cache.set(f"{endpoint}_{data_grouped_hash}", data_grouped)

    def _group_by_and_replace(self, data, param: str, endpoint: str, primary_key=['id']):
        grouped_data_by_param = self._group_by(data, param)
        for data_grouped in grouped_data_by_param:
            if len(data_grouped) > 0:
                data_grouped_params = {param: data_grouped[0][param]}
                data_grouped_hash = hashlib.md5(str(data_grouped_params).encode('utf-8')).hexdigest()
                self.cache.replace(f"{endpoint}_{data_grouped_hash}", data_grouped, primary_key)

    async def _fetch_commodities_prices(self, params):
        endpoint = "/commodities_prices"
        commodities, cached = (await self._fetch_data(endpoint, params=params))
        if not cached:
            if not params or len(params) == 0:
                self._group_by_and_set(commodities, 'id_terminal', endpoint)
                self._group_by_and_set(commodities, 'id', endpoint)
            else:
                primary_key = ['id_commodity', 'id_terminal']
                self._group_by_and_replace(commodities, 'id_terminal', endpoint, primary_key)
                self._group_by_and_replace(commodities, 'id', endpoint, primary_key)
            for commodity in commodities:
                commodity_terminal_params = {'id_commodity': commodity['id'], 'id_terminal': commodity['id_terminal']}
                commodity_terminal_hash = hashlib.md5(str(commodity_terminal_params).encode('utf-8')).hexdigest()
                self.cache.set(f"{endpoint}_{commodity_terminal_hash}", commodity)
        return commodities

    async def _fetch_planets(self, params):
        endpoint = "/planets"
        planets, cached = (await self._fetch_data(endpoint, params=params, ttl=86400))
        if not cached:
            if not params or len(params) == 0:
                self._group_by_and_set(planets, 'id_star_system', endpoint)
                self._group_by_and_set(planets, 'id_faction', endpoint)
                self._group_by_and_set(planets, 'id_jurisdiction', endpoint)
            else:
                self._group_by_and_replace(planets, 'id_star_system', endpoint)
                self._group_by_and_replace(planets, 'id_faction', endpoint)
                self._group_by_and_replace(planets, 'id_jurisdiction', endpoint)
            for planet in planets:
                planet_params = {'id_planet': planet['id']}
                planet_hash = hashlib.md5(str(planet_params).encode('utf-8')).hexdigest()
                self.cache.set(f"{endpoint}_{planet_hash}", planet)
        return planets

    async def _fetch_terminals(self, params):
        endpoint = "/terminals"
        terminals, cached = (await self._fetch_data(endpoint, params=params, ttl=43200))
        if not cached:
            if not params or len(params) == 0:
                self._group_by_and_set(terminals, 'id_star_system', endpoint)
                self._group_by_and_set(terminals, 'id_planet', endpoint)
            else:
                self._group_by_and_replace(terminals, 'id_star_system', endpoint)
                self._group_by_and_replace(terminals, 'id_planet', endpoint)
            for terminal in terminals:
                terminal_params = {'id_terminal': terminal['id']}
                terminal_hash = hashlib.md5(str(terminal_params).encode('utf-8')).hexdigest()
                self.cache.set(f"{endpoint}_{terminal_hash}", terminal)
        return terminals

    async def _fetch_systems(self, params=None):
        endpoint = "/star_systems"
        systems, cached = (await self._fetch_data(endpoint, params, ttl=86400))
        if not cached:
            for system in systems:
                system_params = {'id_star_system': system['id']}
                system_hash = hashlib.md5(str(system_params).encode('utf-8')).hexdigest()
                self.cache.set(f"{endpoint}_{system_hash}", system)
        return systems

    async def _fetch_commodities_routes(self, params):
        endpoint = "/commodities_routes"
        commodities_routes, cached = (await self._fetch_data(endpoint, params))
        if not cached:
            if not params or len(params) == 0:
                self._group_by_and_set(commodities_routes, 'id_terminal_origin', endpoint)
                self._group_by_and_set(commodities_routes, 'id_planet_origin', endpoint)
                self._group_by_and_set(commodities_routes, 'id_orbit_origin', endpoint)
                self._group_by_and_set(commodities_routes, 'id_commodity', endpoint)
            else:
                self._group_by_and_replace(commodities_routes, 'id_terminal_origin', endpoint)
                self._group_by_and_replace(commodities_routes, 'id_planet_origin', endpoint)
                self._group_by_and_replace(commodities_routes, 'id_orbit_origin', endpoint)
                self._group_by_and_replace(commodities_routes, 'id_commodity', endpoint)
            for commodity_route in commodities_routes:
                commodity_route_params = {'id_commodity': commodity_route['id_commodity'],
                                          'id_terminal_origin': commodity_route['id_terminal_origin'],
                                          'id_terminal_destination': commodity_route['id_terminal_destination']}
                commodity_route_hash = hashlib.md5(str(commodity_route_params).encode('utf-8')).hexdigest()
                self.cache.set(f"{endpoint}_{commodity_route_hash}", commodity_route)
        return commodities_routes

    async def _filter_std_commodities(self, commodities):
        selected_version = await self.config_manager.get_version_value()
        return [commodity for commodity in commodities
                if commodity.get("game_version", '0.0') == selected_version]

    async def fetch_commodities_by_id(self, id_commodity):
        params = {'id_commodity': id_commodity}
        commodities = await self._fetch_commodities_prices(params)
        return (await self._filter_std_commodities(commodities))

    async def fetch_commodities_from_terminal(self, id_terminal, id_commodity=None):
        params = {'id_terminal': id_terminal}
        if id_commodity:
            params['id_commodity'] = id_commodity
        commodities = await self._fetch_commodities_prices(params)
        return (await self._filter_std_commodities(commodities))

    def _filter_std_planets(self, planets):
        return [planet for planet in planets
                if planet.get("is_available") == 1]

    async def fetch_planets(self, system_id=None, planet_id=None):
        params = {}
        if system_id:
            params = {'id_star_system': system_id}
        # TODO - if params is only recovering one id, try to get from cache first
        planets = await self._fetch_planets(params)
        return [planet for planet in self._filter_std_planets(planets)
                if (not planet_id or planet.get("id") == planet_id)]

    def _filter_std_terminals(self, terminals):
        return [terminal for terminal in terminals
                if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]

    async def fetch_all_terminals(self):
        params = {}
        terminals = await self._fetch_terminals(params)
        return self._filter_std_terminals(terminals)

    async def fetch_terminals_by_system(self, system_id):
        params = {'id_star_system': system_id}
        terminals = await self._fetch_terminals(params)
        return self._filter_std_terminals(terminals)

    async def fetch_terminals_by_planet(self, planet_id, filtering_terminal=None):
        params = {'id_planet': planet_id}
        # TODO - if params is only recovering one id, try to get from cache first
        terminals = await self._fetch_terminals(params)
        return [terminal for terminal in self._filter_std_terminals(terminals)
                if (not filtering_terminal or terminal.get("id") == filtering_terminal)]

    def _filter_std_systems(self, systems):
        return [system for system in systems
                if system.get("is_available") == 1]

    async def fetch_all_systems(self):
        systems = await self._fetch_systems()
        return self._filter_std_systems(systems)

    async def fetch_systems_from_origin_system(self, origin_system_id, max_bounce=1):
        params = {}
        # TODO - Return systems linked to origin_system_id with a maximum of "max_bounce" hops - API does not give this for now
        systems = await self._fetch_systems(params=params)
        return self._filter_std_systems(systems)

    async def fetch_system(self, system_id):
        # TODO - if params is only recovering one id, try to get from cache first
        systems = await self._fetch_systems()
        return [system for system in self._filter_std_systems(systems)
                if system.get("id") == system_id]

    async def fetch_versions(self):
        return (await self._fetch_data("/game_versions", data_only=False))[0].get("data", {})

    async def perform_trade(self, data):
        """Performs a trade operation (buy/sell)."""
        # TODO - Check if data is formed properly considering user_trades_add endpoint
        return await self._post_data("/user_trades_add/", data)

    async def fetch_distance(self, id_terminal_origin, id_terminal_destination):
        params = {
            'id_terminal_origin': id_terminal_origin,
            'id_terminal_destination': id_terminal_destination
        }
        routes = await self._fetch_commodities_routes(params)
        # TODO - Use next() instead of this loop and filter routes with game_version_origin and game_version_destination
        # selected_version = await self.config_manager.get_version_value()
        for route in routes:
            if route.get("distance", 1) is None:
                return 1
            else:
                return route["distance"]
        return 1

    async def commodity_submit(self, id_commodity_terminal: int, commodities: List[Commodity], details: str):
        # TODO - Check if id_commodity_terminal exists as a commodity terminal

        if not isinstance(commodities, list):
            raise TypeError("commodities must be a list")

        logger = self.get_logger()
        data = {
            "id_terminal": id_commodity_terminal,
            "type": "commodity",
            "prices": [],
            "details": details,
            "game_version": await self.config_manager.get_version_value()
        }
        for commodity in commodities:
            if not isinstance(commodity, Commodity):
                raise TypeError("All elements in commodities must be instances of Commodity")
            price = {
                "id_commodity": commodity.id,
                commodity.get_price_property(): commodity.price,
                "is_missing": commodity.missing,
                commodity.get_scu_property(): commodity.scu,
                commodity.get_status_property(): commodity.status
            }
            data['prices'].append(price)

        logger.debug(f"Submitting commodities to terminal {id_commodity_terminal}")
        return await self._post_data("/data_submit/", data)
