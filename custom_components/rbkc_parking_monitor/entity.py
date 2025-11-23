"""Base entity for RBKC Parking Suspension Monitor."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ParkingDataUpdateCoordinator


class ParkingMonitorEntity(CoordinatorEntity[ParkingDataUpdateCoordinator]):
    """Base entity for RBKC Parking Monitor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ParkingDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="RBKC Parking Monitor",
            manufacturer="RBKC Parking Monitor",
            model="Suspension Monitor",
            sw_version="1.0.0",
        )
