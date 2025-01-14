# global_variables.py
app_name = "UEX-Trader"
cache_db_file = "cache.db"
metrics_db_file = "metrics.db"
config_ini_file = "config.ini"

# hard-coded activable features
trade_tab_activated = True
trade_route_tab_activated = True
best_trade_route_tab_activated = True
submit_tab_activated = False
persistent_cache_activated = True

# Startup Features
load_systems_activated = True
load_planets_activated = True
load_terminals_activated = True
load_commodities_prices_activated = True
load_commodities_routes_activated = True
remove_obsolete_keys_activated = True

# hard-coded entities TTL
system_ttl = 2419200  # Kept one month
planet_ttl = 604800  # Kept one week
terminal_ttl = 86400  # Kept one day
