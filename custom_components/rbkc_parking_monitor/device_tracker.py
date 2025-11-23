"""Device tracker platform for RBKC Parking Suspension Monitor."""
from __future__ import annotations

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

    @property
    def latitude(self) -> float | None:
        """Return latitude of car."""
        coords = self.coordinator.data.get("car_coords")
        return coords[0] if coords else None

    @property
    def longitude(self) -> float | None:
        """Return longitude of car."""
        coords = self.coordinator.data.get("car_coords")
        return coords[1] if coords else None

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def location_name(self) -> str:
        """Return location name."""
        from .const import CONF_CAR_LOCATION
        return self.coordinator.config_entry.data[CONF_CAR_LOCATION]

    @property
    def state(self) -> str | None:
        """Return a human-readable location instead of 'home/away'."""
        return self.location_name or "unknown"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("car_coords") is not None


class SuspensionLocationTracker(ParkingMonitorEntity, TrackerEntity):
    """Tracker for suspension location."""

    _attr_icon = "mdi:alert-circle"

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
    def location_name(self) -> str | None:
        """Return location name."""
        suspension = self._get_suspension_data()
        if suspension:
            return suspension.get("street", f"Suspension {self._index + 1}")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, any]:
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
        return self._get_suspension_data() is not None

    def _get_suspension_data(self) -> dict | None:
        """Get suspension data for this index."""
        map_data = self.coordinator.data.get("map_data", [])
        active_suspensions = [s for s in map_data if s.get("type") == "active"]

        if self._index < len(active_suspensions):
            return active_suspensions[self._index]
        return None
