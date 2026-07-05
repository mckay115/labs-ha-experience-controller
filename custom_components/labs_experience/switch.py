"""Switch pausing and resuming a space's engine."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LabsExperienceConfigEntry
from .engine import SpaceEngine
from .entity import LabsSpaceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LabsExperienceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([LabsAutomationSwitch(entry.runtime_data)])


class LabsAutomationSwitch(LabsSpaceEntity, SwitchEntity, RestoreEntity):
    """Turn off to pause all automatic behavior for the space."""

    _attr_translation_key = "automation"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "automation")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state == STATE_OFF:
            self._engine.async_set_enabled(False)

    @property
    def is_on(self) -> bool:
        return self._engine.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._engine.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._engine.async_set_enabled(False)
