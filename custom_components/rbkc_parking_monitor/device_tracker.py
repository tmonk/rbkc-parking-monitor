"""Device tracker platform for RBKC Parking Suspension Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TRACKER_CAR, MAX_SUSPENSION_TRACKERS
from .coordinator import ParkingDataUpdateCoordinator
from .entity import ParkingMonitorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the device tracker platform."""
    coordinator: ParkingDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create car tracker
    entities = [CarLocationTracker(coordinator)]

    # Create suspension trackers (will be dynamically shown/hidden)
    for i in range(MAX_SUSPENSION_TRACKERS):
        entities.append(SuspensionLocationTracker(coordinator, i))

    async_add_entities(entities)


class CarLocationTracker(ParkingMonitorEntity, TrackerEntity):
    """Tracker for car location."""

    _attr_name = "Car"
    _attr_icon = "mdi:car"

    def __init__(self, coordinator: ParkingDataUpdateCoordinator) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{TRACKER_CAR}"
        self._attr_source_type = SourceType.GPS
        # Keep state/location aligned with configured car location from the start.
        self._attr_location_name = self._get_config_location()
        self._attr_state = self._attr_location_name
        self._attr_latitude = None
        self._attr_longitude = None

    def _get_config_location(self) -> str:
        """Return the configured car location string."""
        return self.coordinator.car_location

    @property
    def latitude(self) -> float | None:
        """Return latitude of car."""
        return self._attr_latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude of car."""
        return self._attr_longitude

    @property
    def state(self) -> str:
        """Force state to the configured location instead of zone home/away."""
        return self._attr_location_name

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return self._attr_source_type

    @property
    def location_name(self) -> str:
        """Return location name."""
        return self._attr_location_name

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose location as an attribute so automations can track changes."""
        return {"location_name": self._get_config_location()}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Available if we have any coordinator data, even without coords
        return self.coordinator.last_update_success or bool(self.coordinator.data)

    def _handle_coordinator_update(self) -> None:
        """Sync state/name with config entry changes."""
        current_loc = self._get_config_location()
        coords = self.coordinator.data.get("car_coords")

        self._attr_location_name = current_loc
        self._attr_state = current_loc
        self._attr_latitude = coords[0] if coords else None
        self._attr_longitude = coords[1] if coords else None

        super()._handle_coordinator_update()


class SuspensionLocationTracker(ParkingMonitorEntity, TrackerEntity):
    """Tracker for suspension location."""

    def __init__(
        self, coordinator: ParkingDataUpdateCoordinator, index: int
    ) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_sus_active_{index}"
        )
        self._attr_name = f"Suspension {index + 1}"

    @property
    def latitude(self) -> float | None:
        """Return latitude of suspension."""
        suspension = self._get_suspension_data()
        if suspension and "coords" in suspension:
            return suspension["coords"][0]
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude of suspension."""
        suspension = self._get_suspension_data()
        if suspension and "coords" in suspension:
            return suspension["coords"][1]
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def location_name(self) -> str:
        """Return location name."""
        suspension = self._get_suspension_data()
        if suspension:
            return suspension.get("street", f"Suspension {self._index + 1}")
        return "No Suspension"

    @property
    def state(self) -> str:
        """Return the state of the tracker."""
        if self._get_suspension_data():
            return self.location_name
        return "No Suspension"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self._get_suspension_data():
            return "mdi:alert-circle"
        return "mdi:minus-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        suspension = self._get_suspension_data()
        if suspension:
            return {
                "description": suspension.get("desc", ""),
                "type": suspension.get("type", ""),
                "street": suspension.get("street", ""),
            }
        return {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Available if coordinator is happy, even if no suspension
        return self.coordinator.last_update_success or bool(self.coordinator.data)

    def _get_suspension_data(self) -> dict | None:
        """Get suspension data for this index."""
        map_data = self.coordinator.data.get("map_data", [])
        active_suspensions = [s for s in map_data if s.get("type") == "active"]

        if self._index < len(active_suspensions):
            return active_suspensions[self._index]
        return None
