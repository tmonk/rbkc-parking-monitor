"""Repairs platform for RBKC Parking Monitor."""
from __future__ import annotations

from typing import cast

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


async def async_create_dashboard_issue(hass: HomeAssistant) -> None:
    """Create a repair issue to prompt dashboard setup."""
    # Check if lovelace dashboards exist
    lovelace_dashboards = hass.data.get("lovelace", {}).get("dashboards", {})

    # Check if our dashboard is already configured
    dashboard_exists = any(
        "parking" in dash_id.lower() or "rbkc" in dash_id.lower()
        for dash_id in lovelace_dashboards.keys()
    )

    if not dashboard_exists:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "dashboard_not_configured",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="dashboard_not_configured",
            translation_placeholders={
                "package_config": (
                    "homeassistant:\n"
                    "  packages:\n"
                    "    rbkc_parking: !include custom_components/rbkc_parking_monitor/package.yaml"
                ),
                "direct_config": (
                    "lovelace:\n"
                    "  dashboards:\n"
                    "    parking-monitor:\n"
                    "      mode: yaml\n"
                    "      title: Parking Monitor\n"
                    "      icon: mdi:car\n"
                    "      show_in_sidebar: true\n"
                    "      filename: custom_components/rbkc_parking_monitor/dashboard.yaml"
                ),
            },
        )


async def async_delete_dashboard_issue(hass: HomeAssistant) -> None:
    """Delete the dashboard repair issue."""
    ir.async_delete_issue(hass, DOMAIN, "dashboard_not_configured")
