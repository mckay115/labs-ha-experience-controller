"""Sidebar panel registration for the Spaces overview."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

PANEL_URL_PATH = "labs-spaces"
PANEL_ASSET_URL = f"/{DOMAIN}/panel.js"
DATA_PANEL = f"{DOMAIN}_panel"
DATA_STATIC = f"{DOMAIN}_static"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the Spaces sidebar panel (idempotent)."""
    if not hass.data.get(DATA_STATIC):
        hass.data[DATA_STATIC] = True
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    PANEL_ASSET_URL,
                    str(Path(__file__).parent / "panel.js"),
                    cache_headers=False,
                )
            ]
        )
    if hass.data.get(DATA_PANEL):
        return
    hass.data[DATA_PANEL] = True
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Spaces",
        sidebar_icon="mdi:floor-plan",
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "labs-experience-panel",
                "module_url": PANEL_ASSET_URL,
                "embed_iframe": False,
            }
        },
        require_admin=False,
    )


@callback
def async_unregister_panel(hass: HomeAssistant) -> None:
    if hass.data.pop(DATA_PANEL, None):
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
