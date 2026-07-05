"""Sensor exposing a space's occupancy phase."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LabsExperienceConfigEntry
from .circadian import circadian_targets, sun_factor
from .const import Daypart, Phase
from .engine import SpaceEngine
from .entity import LabsSpaceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LabsExperienceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    engine = entry.runtime_data
    async_add_entities([LabsPhaseSensor(engine), LabsDaypartSensor(engine)])


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
            "lighting": self._engine.lighting.authority.value,
            "climate": self._engine.climate.authority.value,
            "window_paused": self._engine.climate.window_paused,
        }


class LabsDaypartSensor(LabsSpaceEntity, SensorEntity):
    """The space's time-of-body layer, with live circadian targets."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "daypart"
    _attr_options = [daypart.value for daypart in Daypart]

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "daypart")

    @property
    def native_value(self) -> str:
        return self._engine.daypart.value

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        config = self._engine.config
        kelvin, brightness = circadian_targets(
            self._engine.hass,
            self._engine.daypart,
            min_kelvin=config.min_kelvin,
            max_kelvin=config.max_kelvin,
            min_brightness=config.min_brightness,
            max_brightness=config.max_brightness,
        )
        return {
            "circadian_kelvin": kelvin,
            "circadian_brightness": brightness,
            "sun_factor": sun_factor(self._engine.hass),
        }
