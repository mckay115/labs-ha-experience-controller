"""The Labs Experience Controller integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .engine import SpaceEngine

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type LabsExperienceConfigEntry = ConfigEntry[SpaceEngine]


async def async_setup_entry(
    hass: HomeAssistant, entry: LabsExperienceConfigEntry
) -> bool:
    """Set up a space from a config entry."""
    engine = SpaceEngine(hass, entry)
    entry.runtime_data = engine
    await engine.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: LabsExperienceConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: LabsExperienceConfigEntry
) -> bool:
    """Unload a space."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.async_stop()
    return unload_ok
