"""Diagnostics for Labs Experience Controller."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import LabsExperienceConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LabsExperienceConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a space."""
    return {
        "data": dict(entry.data),
        "options": dict(entry.options),
        "engine": entry.runtime_data.snapshot(),
    }
