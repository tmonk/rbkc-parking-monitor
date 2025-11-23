import unittest
from unittest.mock import MagicMock

# Mock Home Assistant dependencies
class MockCoordinator:
    def __init__(self, data=None, success=True):
        self.data = data if data is not None else {}
        self.last_update_success = success
        self.config_entry = MagicMock()
        self.config_entry.entry_id = "test_entry"

class MockEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator
    
    @property
    def available(self):
        return self.coordinator.last_update_success

# Copy logic from device_tracker.py (SuspensionLocationTracker)
class SuspensionLocationTracker(MockEntity):
    def __init__(self, coordinator, index):
        super().__init__(coordinator)
        self._index = index

    def _get_suspension_data(self) -> dict | None:
        """Get suspension data for this index."""
        map_data = self.coordinator.data.get("map_data", [])
        active_suspensions = [s for s in map_data if s.get("type") == "active"]

        if self._index < len(active_suspensions):
            return active_suspensions[self._index]
        return None

    # NEW Logic
    @property
    def available(self) -> bool:
        # Available if coordinator is happy
        return self.coordinator.last_update_success or bool(self.coordinator.data)
    
    # OLD Logic (for comparison/verification of bug)
    def available_old(self) -> bool:
        return self._get_suspension_data() is not None

    @property
    def location_name(self) -> str:
        suspension = self._get_suspension_data()
        if suspension:
            return suspension.get("street", f"Suspension {self._index + 1}")
        return "No Suspension"

    @property
    def state(self) -> str:
        if self._get_suspension_data():
            return self.location_name
        return "No Suspension"

class TestAvailability(unittest.TestCase):
    def test_suspension_tracker_unavailable_bug(self):
        # Case: No suspensions found, but update successful
        data = {
            "map_data": [], # No active suspensions
            "status": "OK"
        }
        coord = MockCoordinator(data=data, success=True)
        tracker = SuspensionLocationTracker(coord, 0)

        # Old logic: Unavailable because no data for index 0
        self.assertFalse(tracker.available_old(), "Old logic should be unavailable when no suspension")

        # New logic: Available because coordinator has data
        self.assertTrue(tracker.available, "New logic should be available even if no suspension")
        self.assertEqual(tracker.state, "No Suspension")
        self.assertEqual(tracker.location_name, "No Suspension")

    def test_suspension_tracker_with_data(self):
        # Case: 1 Active suspension
        data = {
            "map_data": [{"type": "active", "street": "High St"}],
            "status": "OK"
        }
        coord = MockCoordinator(data=data, success=True)
        tracker_0 = SuspensionLocationTracker(coord, 0)
        tracker_1 = SuspensionLocationTracker(coord, 1)

        # Index 0 has data
        self.assertTrue(tracker_0.available)
        self.assertEqual(tracker_0.state, "High St")

        # Index 1 has no data
        # Old logic: Unavailable
        self.assertFalse(tracker_1.available_old())
        # New logic: Available (as 'No Suspension')
        self.assertTrue(tracker_1.available)
        self.assertEqual(tracker_1.state, "No Suspension")

    def test_binary_sensor_availability(self):
        # Mocking binary sensor logic
        data = {}
        coord = MockCoordinator(data=data, success=False) # Update failed, no data
        
        # Logic: return self.coordinator.last_update_success or bool(self.coordinator.data)
        available = coord.last_update_success or bool(coord.data)
        self.assertFalse(available)

        # Update success, empty data
        coord = MockCoordinator(data={}, success=True)
        available = coord.last_update_success or bool(coord.data)
        self.assertTrue(available)

        # Update failed, but stale data exists
        coord = MockCoordinator(data={"some": "data"}, success=False)
        available = coord.last_update_success or bool(coord.data)
        self.assertTrue(available)

if __name__ == '__main__':
    unittest.main()
