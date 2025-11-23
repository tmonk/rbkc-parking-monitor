"""The RBKC Parking Suspension Monitor integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    IMAP_EVENT,
    CONF_CAR_LOCATION,
    CONF_DEBUG_MODE,
)
from .coordinator import ParkingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]

# Service schemas
CHECK_PARKING_SCHEMA = vol.Schema(
    {
        vol.Optional("email_body"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RBKC Parking Suspension Monitor from a config entry."""
    # Create coordinator
    coordinator = ParkingDataUpdateCoordinator(hass, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register IMAP event listener
    async def handle_imap_event(event):
        """Handle incoming IMAP email events."""
        email_body = event.data.get("text", "")
        if email_body:
            _LOGGER.info("Received IMAP event, processing email")
            await coordinator.async_process_email(email_body)

            # Send notification if car at risk
            if coordinator.data.get("car_at_risk_now"):
                await hass.services.async_call(
                    "notify",
                    "notify",
                    {
                        "title": "🚨 MOVE CAR NOW",
                        "message": f"Active suspension at {entry.data[CONF_CAR_LOCATION]}! \n\n"
                        + "\n".join(coordinator.data.get("my_active_suspensions", [])),
                        "data": {"color": "#FF0000"},
                    },
                )
            elif coordinator.data.get("car_at_risk_soon"):
                await hass.services.async_call(
                    "notify",
                    "notify",
                    {
                        "title": "⚠️ Upcoming Suspension",
                        "message": f"Plan ahead! Suspension starts this week at {entry.data[CONF_CAR_LOCATION]}. \n\n"
                        + "\n".join(coordinator.data.get("my_upcoming_suspensions", [])),
                    },
                )

    entry.async_on_unload(hass.bus.async_listen(IMAP_EVENT, handle_imap_event))

    # Register check_parking service
    async def async_check_parking(call: ServiceCall) -> None:
        """Handle check_parking service call."""
        email_body = call.data.get("email_body")
        await coordinator.async_manual_check(email_body=email_body)

    hass.services.async_register(
        DOMAIN,
        "check_parking",
        async_check_parking,
        schema=CHECK_PARKING_SCHEMA,
    )

    # Register dashboard
    await async_register_dashboard(hass)

    # Set up reload listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Shutdown coordinator
        coordinator: ParkingDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()

        # Remove coordinator
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unregister service if no more instances
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "check_parking")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_register_dashboard(hass: HomeAssistant) -> None:
    """Register the parking monitor dashboard as a panel."""
    try:
        # Dashboard content to inject
        dashboard_file = Path(__file__).parent / "dashboard.yaml"

        if not dashboard_file.exists():
            _LOGGER.warning("Dashboard file not found: %s", dashboard_file)
            return

        # Read dashboard YAML
        dashboard_yaml = await hass.async_add_executor_job(dashboard_file.read_text)

        # Parse YAML to extract views
        import yaml
        dashboard_data = yaml.safe_load(dashboard_yaml)

        # Register as a lovelace panel with custom config
        hass.components.frontend.async_register_built_in_panel(
            component_name="lovelace",
            sidebar_title="Parking Monitor",
            sidebar_icon="mdi:car",
            frontend_url_path=f"{DOMAIN}_dashboard",
            config={
                "mode": "storage",
            },
            require_admin=False,
        )

        # Initialize lovelace config for this panel
        from homeassistant.components.lovelace import dashboard as dash_module

        panel_url = f"{DOMAIN}_dashboard"

        # Create the dashboard configuration
        await dash_module.async_create_dashboard(
            hass=hass,
            url_path=panel_url,
            config={
                "mode": "storage",
                "title": "Parking Monitor",
                "icon": "mdi:car",
                "show_in_sidebar": True,
                "require_admin": False,
            },
        )

        # Get the dashboard instance and save config
        if "lovelace" in hass.data and "dashboards" in hass.data["lovelace"]:
            dashboards = hass.data["lovelace"]["dashboards"]
            if panel_url in dashboards:
                dashboard_instance = dashboards[panel_url]
                # Save the views to the dashboard
                await dashboard_instance.async_save(dashboard_data)
                _LOGGER.info("Parking Monitor dashboard registered successfully")
            else:
                _LOGGER.warning("Dashboard instance not found after creation")
        else:
            _LOGGER.warning("Lovelace not initialized, dashboard config not saved")

    except Exception as err:
        _LOGGER.error("Failed to register dashboard: %s", err)
        _LOGGER.debug("Dashboard registration error details", exc_info=True)
