"""Config flow for RBKC Parking Suspension Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_CAR_LOCATION,
    CONF_DEBUG_MODE,
    CONF_PROXIMITY_THRESHOLD,
    CONF_UPCOMING_WINDOW_DAYS,
    DEFAULT_CAR_LOCATION,
    DEFAULT_DEBUG_MODE,
    DEFAULT_PROXIMITY_THRESHOLD,
    DEFAULT_UPCOMING_WINDOW_DAYS,
)

_LOGGER = logging.getLogger(__name__)


class RBKCParkingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RBKC Parking Suspension Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate car location is not empty
            if not user_input[CONF_CAR_LOCATION].strip():
                errors[CONF_CAR_LOCATION] = "car_location_required"
            else:
                # Create entry
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="RBKC Parking Monitor",
                    data=user_input,
                )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CAR_LOCATION,
                    default=user_input.get(CONF_CAR_LOCATION, DEFAULT_CAR_LOCATION)
                    if user_input
                    else DEFAULT_CAR_LOCATION,
                ): cv.string,
                vol.Optional(
                    CONF_PROXIMITY_THRESHOLD,
                    default=user_input.get(
                        CONF_PROXIMITY_THRESHOLD, DEFAULT_PROXIMITY_THRESHOLD
                    )
                    if user_input
                    else DEFAULT_PROXIMITY_THRESHOLD,
                ): cv.positive_int,
                vol.Optional(
                    CONF_UPCOMING_WINDOW_DAYS,
                    default=user_input.get(
                        CONF_UPCOMING_WINDOW_DAYS, DEFAULT_UPCOMING_WINDOW_DAYS
                    )
                    if user_input
                    else DEFAULT_UPCOMING_WINDOW_DAYS,
                ): cv.positive_int,
                vol.Optional(
                    CONF_DEBUG_MODE,
                    default=user_input.get(CONF_DEBUG_MODE, DEFAULT_DEBUG_MODE)
                    if user_input
                    else DEFAULT_DEBUG_MODE,
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> RBKCParkingOptionsFlow:
        """Get the options flow for this handler."""
        return RBKCParkingOptionsFlow(config_entry)


class RBKCParkingOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for RBKC Parking Suspension Monitor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate car location is not empty
            if not user_input[CONF_CAR_LOCATION].strip():
                errors[CONF_CAR_LOCATION] = "car_location_required"
            else:
                # Update config entry data
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data=user_input,
                )

                # Trigger coordinator to update with new config when available.
                coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
                if coordinator:
                    await coordinator.async_update_config(
                        car_location=user_input[CONF_CAR_LOCATION],
                        proximity_threshold=user_input[CONF_PROXIMITY_THRESHOLD],
                        upcoming_window_days=user_input[CONF_UPCOMING_WINDOW_DAYS],
                        debug_mode=user_input[CONF_DEBUG_MODE],
                    )
                    await coordinator.async_manual_check()
                else:
                    # If not loaded yet, reload entry so new data takes effect.
                    await self.hass.config_entries.async_reload(self._config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        # Get current values
        current_data = self._config_entry.data

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CAR_LOCATION,
                    default=current_data.get(CONF_CAR_LOCATION, DEFAULT_CAR_LOCATION),
                ): cv.string,
                vol.Optional(
                    CONF_PROXIMITY_THRESHOLD,
                    default=current_data.get(
                        CONF_PROXIMITY_THRESHOLD, DEFAULT_PROXIMITY_THRESHOLD
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_UPCOMING_WINDOW_DAYS,
                    default=current_data.get(
                        CONF_UPCOMING_WINDOW_DAYS, DEFAULT_UPCOMING_WINDOW_DAYS
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_DEBUG_MODE,
                    default=current_data.get(CONF_DEBUG_MODE, DEFAULT_DEBUG_MODE),
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
