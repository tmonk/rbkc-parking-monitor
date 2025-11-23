"""Constants for the RBKC Parking Suspension Monitor integration."""
from typing import Final

DOMAIN: Final = "rbkc_parking_monitor"

# Configuration
CONF_CAR_LOCATION: Final = "car_location"
CONF_DEBUG_MODE: Final = "debug_mode"
CONF_PROXIMITY_THRESHOLD: Final = "proximity_threshold"
CONF_UPCOMING_WINDOW_DAYS: Final = "upcoming_window_days"

# Defaults
DEFAULT_CAR_LOCATION: Final = "Town Hall, Hornton Street"
DEFAULT_DEBUG_MODE: Final = False
DEFAULT_PROXIMITY_THRESHOLD: Final = 100  # meters
DEFAULT_UPCOMING_WINDOW_DAYS: Final = 7  # days

# Files
CACHE_FILE: Final = "parking_email_cache.txt"
GEO_CACHE_FILE: Final = "parking_geo_cache.json"

# Geocoding
GEOCODE_REGION: Final = "Kensington and Chelsea, London, UK"
GEOCODE_USER_AGENT: Final = "HomeAssistant_Parking_Monitor/1.0"
GEOCODE_TIMEOUT: Final = 5  # seconds
GEOCODE_RATE_LIMIT: Final = 1  # seconds between requests

# Update intervals
UPDATE_INTERVAL_HOURS: Final = 24  # Daily update at 8am handled by time trigger
IMAP_EVENT: Final = "imap_content"

# Device tracker
TRACKER_CAR: Final = "parking_monitor_car"
TRACKER_SUSPENSION_PREFIX: Final = "sus_active_"
MAX_SUSPENSION_TRACKERS: Final = 5

# Earth radius in meters for distance calculations
EARTH_RADIUS_METERS: Final = 6371000
