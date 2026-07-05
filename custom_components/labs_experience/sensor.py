"""Sensor exposing a space's occupancy phase."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LabsExperienceConfigEntry
from .const import Phase
from .engine import SpaceEngine
from .entity import LabsSpaceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LabsExperienceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([LabsPhaseSensor(entry.runtime_data)])


class LabsPhaseSensor(LabsSpaceEntity, SensorEntity):
    """Where the space is in its occupancy lifecycle."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "phase"
    _attr_options = [phase.value for phase in Phase]

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "phase")

    @property
    def native_value(self) -> str:
        return self._engine.phase.value

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "since": self._engine.phase_since,
            "active_presence": self._engine.active_presence,
            "experience": self._engine.active_state.name
            if self._engine.active_state
            else None,
            "override": self._engine.override_id is not None,
        }
