# api.py
import logging
import aiohttp
import json
from cache_manager import CacheManager
import asyncio
import traceback
import hashlib


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

    async def _fetch_data(self, endpoint, params=None):
        await self.ensure_initialized()
        hashed_params = hashlib.md5(str(params).encode('utf-8')).hexdigest()
        cache_key = f"{endpoint}_{hashed_params}"
        cached_data = self.cache.get(cache_key, int(self.config_manager.get_ttl()))
        logger = self.get_logger()
        if cached_data:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_data
        url = f"{await self.get_api_base_url()}{endpoint}"
        logger.debug(f"API Request: GET {url} {params if params else ''}")
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.cache.set(cache_key, data)
                    return data
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

    async def fetch_commodities_by_id(self, id_commodity):
        params = {'id_commodity': id_commodity}
        commodities = await self._fetch_data("/commodities_prices", params=params)
        selected_version = await self.config_manager.get_version_value()
        return [commodity for commodity in commodities.get("data", [])
                if commodity.get("game_version", '0.0') == selected_version]

    async def fetch_commodities_from_terminal(self, id_terminal, id_commodity=None):
        params = {'id_terminal': id_terminal}
        if id_commodity:
            params['id_commodity'] = id_commodity
        commodities = await self._fetch_data("/commodities_prices", params=params)
        selected_version = await self.config_manager.get_version_value()
        return [commodity for commodity in commodities.get("data", [])
                if commodity.get("game_version", '0.0') == selected_version]

    async def fetch_planets(self, system_id=None, planet_id=None):
        params = {}
        if system_id:
            params = {'id_star_system': system_id}
        planets = await self._fetch_data("/planets", params=params)
        return [planet for planet in planets.get("data", [])
                if planet.get("is_available") == 1 and (not planet_id or planet.get("id") == planet_id)]

    async def fetch_terminals(self, system_id, planet_id=None, terminal_id=None):
        params = {'id_star_system': system_id}
        if planet_id:
            params['id_planet'] = planet_id
        terminals = await self._fetch_data("/terminals", params=params)
        return [terminal for terminal in terminals.get("data", [])
                if terminal.get("type") == "commodity" and terminal.get("is_available") == 1
                and (not terminal_id or terminal.get("id") == terminal_id)]

    async def fetch_terminals_from_planet(self, planet_id):
        params = {'id_planet': planet_id}
        terminals = await self._fetch_data("/terminals", params=params)
        return [terminal for terminal in terminals.get("data", [])
                if terminal.get("type") == "commodity" and terminal.get("is_available") == 1]

    async def fetch_all_systems(self):
        systems = await self._fetch_data("/star_systems")
        return [system for system in systems.get("data", [])
                if system.get("is_available") == 1]

    async def fetch_systems_from_origin_system(self, origin_system_id, max_bounce=1):
        params = {}
        # TODO - Return systems linked to origin_system_id with a maximum of "max_bounce" hops - API does not give this for now
        systems = await self._fetch_data("/star_systems", params=params)
        return [system for system in systems.get("data", [])
                if system.get("is_available") == 1]

    async def fetch_system(self, system_id):
        params = {}
        systems = await self._fetch_data("/star_systems", params=params)
        return [system for system in systems.get("data", [])
                if system.get("is_available") == 1
                and system.get("id") == system_id]

    async def fetch_unknown_terminals_from_system(self, id_system):
        params = {'id_star_system': id_system}
        terminals = (await self._fetch_data("/terminals", params=params)).get("data", [])
        return [terminal for terminal in terminals
                if terminal.get("id_planet") == 0 and terminal.get("is_available") == 1]

    async def fetch_versions(self):
        return (await self._fetch_data("/game_versions")).get("data", {})

    async def perform_trade(self, data):
        """Performs a trade operation (buy/sell)."""
        # TODO - Check if data is formed properly considering user_trades_add endpoint
        return await self._post_data("/user_trades_add/", data)

    async def fetch_distance(self, id_terminal_origin, id_terminal_destination):
        params = {
            'id_terminal_origin': id_terminal_origin,
            'id_terminal_destination': id_terminal_destination
        }
        routes = await self._fetch_data("/commodities_routes", params=params)
        # TODO - Use next() instead of this loop and filter routes with game_version_origin and game_version_destination
        # selected_version = await self.config_manager.get_version_value()
        for route in routes.get("data", []):
            if route.get("distance", 1) is None:
                return 1
            else:
                return route["distance"]
        return 1
