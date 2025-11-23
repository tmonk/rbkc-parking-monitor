"""DataUpdateCoordinator for RBKC Parking Suspension Monitor."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    UPDATE_INTERVAL_HOURS,
    CONF_CAR_LOCATION,
    CONF_PROXIMITY_THRESHOLD,
    CONF_UPCOMING_WINDOW_DAYS,
    CONF_DEBUG_MODE,
)
from .parking_api import ParkingApiClient

_LOGGER = logging.getLogger(__name__)


class ParkingDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching parking suspension data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self.client = ParkingApiClient(
            hass,
            car_location=entry.data[CONF_CAR_LOCATION],
            proximity_threshold=entry.data[CONF_PROXIMITY_THRESHOLD],
            upcoming_window_days=entry.data[CONF_UPCOMING_WINDOW_DAYS],
            debug_mode=entry.data.get(CONF_DEBUG_MODE, False),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API (scheduled updates)."""
        try:
            _LOGGER.debug("Running scheduled parking check")
            return await self.client.async_check_parking()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_process_email(self, email_body: str) -> None:
        """Process a new email and update data immediately."""
        try:
            _LOGGER.info("Processing new IMAP email event")
            data = await self.client.async_check_parking(email_body=email_body)
            self.async_set_updated_data(data)
        except Exception as err:
            _LOGGER.error("Error processing email: %s", err)
            raise UpdateFailed(f"Error processing email: {err}") from err

    async def async_manual_check(
        self, email_body: str | None = None
    ) -> dict[str, Any]:
        """Manually trigger a parking check (service call)."""
        try:
            _LOGGER.info("Manual parking check triggered")
            data = await self.client.async_check_parking(email_body=email_body)
            self.async_set_updated_data(data)
            return data
        except Exception as err:
            _LOGGER.error("Error in manual check: %s", err)
            raise UpdateFailed(f"Error in manual check: {err}") from err

    async def async_update_config(
        self,
        car_location: str | None = None,
        proximity_threshold: int | None = None,
        upcoming_window_days: int | None = None,
        debug_mode: bool | None = None,
    ) -> None:
        """Update configuration and recreate client."""
        # Update entry data
        new_data = dict(self.config_entry.data)
        if car_location is not None:
            new_data[CONF_CAR_LOCATION] = car_location
        if proximity_threshold is not None:
            new_data[CONF_PROXIMITY_THRESHOLD] = proximity_threshold
        if upcoming_window_days is not None:
            new_data[CONF_UPCOMING_WINDOW_DAYS] = upcoming_window_days
        if debug_mode is not None:
            new_data[CONF_DEBUG_MODE] = debug_mode

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

        # Recreate client with new config
        await self.client.async_close()
        self.client = ParkingApiClient(
            self.hass,
            car_location=new_data[CONF_CAR_LOCATION],
            proximity_threshold=new_data[CONF_PROXIMITY_THRESHOLD],
            upcoming_window_days=new_data[CONF_UPCOMING_WINDOW_DAYS],
            debug_mode=new_data.get(CONF_DEBUG_MODE, False),
        )

        # Trigger an update so entities pick up the new location immediately
        # even if the next fetch doesn't change payload content.
        self.async_set_updated_data(self.data or {})
        await self.async_refresh()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.client.async_close()
