"""Binary sensor platform for RBKC Parking Suspension Monitor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ParkingDataUpdateCoordinator
from .entity import ParkingMonitorEntity


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
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        data = self.coordinator.data

        # Format suspension lists
        my_active = data.get("my_active_suspensions", [])
        my_upcoming = data.get("my_upcoming_suspensions", [])
        all_active = data.get("all_active_suspensions", [])
        all_upcoming = data.get("all_upcoming_suspensions", [])

        return {
            "active_suspensions": "\n".join(my_active) if my_active else "None",
            "upcoming_suspensions": "\n".join(my_upcoming) if my_upcoming else "None",
            "upcoming_risk": data.get("car_at_risk_soon", False),
            "all_active_suspensions": "\n".join(all_active) if all_active else "_No active suspensions found_",
            "all_upcoming_suspensions": "\n".join(all_upcoming) if all_upcoming else "_No upcoming suspensions found_",
            "last_status": data.get("status", "Unknown"),
            "email_data_date": data.get("email_timestamp", "Unknown"),
            "last_checked": data.get("last_checked", "Never"),
        }
