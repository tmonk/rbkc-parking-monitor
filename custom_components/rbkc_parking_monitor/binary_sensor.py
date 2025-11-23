"""Binary sensor platform for RBKC Parking Suspension Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging

from .const import DOMAIN
from .coordinator import ParkingDataUpdateCoordinator
from .entity import ParkingMonitorEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: ParkingDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CarInSuspendedBaySensor(coordinator)])


class CarInSuspendedBaySensor(ParkingMonitorEntity, BinarySensorEntity):
    """Binary sensor for car in suspended bay."""

    _attr_name = "Car in Suspended Bay"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: ParkingDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_car_in_suspended_bay"

    @property
    def is_on(self) -> bool:
        """Return true if car is at risk now."""
        return self.coordinator.data.get("car_at_risk_now", False)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Available if we have any data, even if last update failed
        return self.coordinator.last_update_success or bool(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        data = self.coordinator.data or {}

        # Format suspension lists (keep as lists for templating)
        my_active = data.get("my_active_suspensions") or []
        my_upcoming = data.get("my_upcoming_suspensions") or []
        all_active = data.get("all_active_suspensions") or ["_No active suspensions found_"]
        all_upcoming = data.get("all_upcoming_suspensions") or ["_No upcoming suspensions found_"]

        try:
            _LOGGER.info(
                (
                    "Binary sensor attrs: status=%s active=%d upcoming=%d "
                    "my_active=%d my_upcoming=%d email=%s last_checked=%s"
                ),
                data.get("status"),
                len(all_active),
                len(all_upcoming),
                len(my_active),
                len(my_upcoming),
                data.get("email_timestamp"),
                data.get("last_checked"),
            )
        except Exception:
            _LOGGER.debug("Binary sensor attrs logging failed; data=%s", data)

        return {
            "active_suspensions": my_active,
            "upcoming_suspensions": my_upcoming,
            "upcoming_risk": data.get("car_at_risk_soon", False),
            "all_active_suspensions": all_active,
            "all_upcoming_suspensions": all_upcoming,
            "last_status": data.get("status", "Unknown"),
            "email_data_date": data.get("email_timestamp", "Unknown"),
            "last_checked": data.get("last_checked", "Never"),
        }
