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

    # Set up reload listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Automatically create dashboard in storage
    await async_create_dashboard(hass)

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


async def async_create_dashboard(hass: HomeAssistant) -> None:
    """Add package reference to configuration.yaml."""
    try:
        import yaml
        from ruamel.yaml import YAML

        config_path = Path(hass.config.config_dir) / "configuration.yaml"
        package_line = "rbkc_parking: !include custom_components/rbkc_parking_monitor/package.yaml"

        if not config_path.exists():
            _LOGGER.warning("configuration.yaml not found")
            return

        # Read current configuration
        config_content = await hass.async_add_executor_job(config_path.read_text)

        # Check if already added
        if "rbkc_parking_monitor/package.yaml" in config_content:
            _LOGGER.debug("Package already referenced in configuration.yaml")
            return

        # Parse YAML with ruamel to preserve formatting
        yaml_parser = YAML()
        yaml_parser.preserve_quotes = True
        yaml_parser.default_flow_style = False

        config_data = yaml_parser.load(config_content)

        # Ensure homeassistant section exists
        if "homeassistant" not in config_data:
            config_data["homeassistant"] = {}

        # Check packages configuration
        ha_config = config_data["homeassistant"]

        # If packages doesn't exist or is not a dict (e.g., it's !include_dir_named)
        if "packages" not in ha_config:
            # Create packages dict
            ha_config["packages"] = {}
        elif not isinstance(ha_config["packages"], dict):
            # packages is a tag (like !include_dir_named), we need to restructure it
            _LOGGER.info(
                "configuration.yaml uses packages with !include directive. "
                "Restructuring to add our package while preserving existing includes."
            )
            # Store the existing include directive
            existing_packages = ha_config["packages"]
            # Convert to a dict with both our package and their existing includes
            ha_config["packages"] = {
                "existing_packages": existing_packages
            }

        # Add our package reference if not already there
        if "rbkc_parking" not in ha_config["packages"]:
            from ruamel.yaml.scalarstring import PreservedScalarString

            # Add the include reference
            ha_config["packages"]["rbkc_parking"] = PreservedScalarString(
                "!include custom_components/rbkc_parking_monitor/package.yaml"
            )

            # Write back to file
            backup_path = config_path.with_suffix(".yaml.backup")
            await hass.async_add_executor_job(
                lambda: config_path.rename(backup_path)
            )

            with open(config_path, "w") as f:
                yaml_parser.dump(config_data, f)

            _LOGGER.info(
                "Added package reference to configuration.yaml. "
                "Backup saved to %s. Restart required.",
                backup_path
            )

            # Create persistent notification
            hass.components.persistent_notification.async_create(
                "RBKC Parking Monitor has added the dashboard configuration to your "
                "configuration.yaml. **Please restart Home Assistant** to see the dashboard "
                "in your sidebar.\n\nA backup of your configuration was saved to "
                f"`configuration.yaml.backup`.",
                title="RBKC Parking Monitor - Restart Required",
                notification_id=f"{DOMAIN}_dashboard_added",
            )

    except ImportError:
        _LOGGER.error(
            "ruamel.yaml not available. Cannot automatically modify configuration.yaml. "
            "Please manually add the package reference."
        )
    except Exception as err:
        _LOGGER.error("Failed to modify configuration.yaml: %s", err)
        _LOGGER.debug("Configuration modification error", exc_info=True)
