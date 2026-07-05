"""Button clearing a space's manual experience override."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LabsExperienceConfigEntry
from .engine import SpaceEngine
from .entity import LabsSpaceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LabsExperienceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([LabsResumeAutomaticButton(entry.runtime_data)])


class LabsResumeAutomaticButton(LabsSpaceEntity, ButtonEntity):
    """Return the space to automatic experience selection."""

    _attr_translation_key = "resume_automatic"

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "resume_automatic")

    async def async_press(self) -> None:
        self._engine.async_set_override(None)
