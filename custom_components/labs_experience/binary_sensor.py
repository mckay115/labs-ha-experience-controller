"""Binary sensor exposing a space's occupancy."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    async_add_entities([LabsOccupiedBinarySensor(entry.runtime_data)])


class LabsOccupiedBinarySensor(LabsSpaceEntity, BinarySensorEntity):
    """On while the space is waking or occupied."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_translation_key = "occupied"

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "occupied")

    @property
    def is_on(self) -> bool:
        return self._engine.phase in (Phase.WAKING, Phase.OCCUPIED)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "phase": self._engine.phase.value,
            "presence_detected": self._engine.presence_active,
        }
