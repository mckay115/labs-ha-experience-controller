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
    engine = entry.runtime_data
    entities: list[LabsSpaceEntity] = [LabsAutomationSwitch(engine)]
    if engine.config.all_profile_lights:
        entities.append(LabsCircadianSwitch(engine))
    async_add_entities(entities)


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


class LabsCircadianSwitch(LabsSpaceEntity, SwitchEntity, RestoreEntity):
    """Enable or disable circadian color/brightness drift for the space."""

    _attr_translation_key = "circadian"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "circadian")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state == STATE_OFF:
            self._engine.lighting.circadian_enabled = False

    @property
    def is_on(self) -> bool:
        return self._engine.lighting.circadian_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._engine.lighting.circadian_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._engine.lighting.circadian_enabled = False
        self.async_write_ha_state()
