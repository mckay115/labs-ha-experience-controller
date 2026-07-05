"""Select entity exposing and overriding a space's experience state."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LabsExperienceConfigEntry
from .const import (
    ATTR_STATE,
    SERVICE_CLEAR_OVERRIDE,
    SERVICE_SET_STATE,
    Authority,
    Phase,
)
from .engine import SpaceEngine
from .entity import LabsSpaceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LabsExperienceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    engine = entry.runtime_data
    entities: list[LabsSpaceEntity] = [LabsExperienceSelect(engine)]
    if engine.config.all_profile_lights:
        entities.append(LabsLightingSelect(engine))
    async_add_entities(entities)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_STATE, {vol.Required(ATTR_STATE): cv.string}, "async_set_state"
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_OVERRIDE, None, "async_clear_override"
    )


class LabsExperienceSelect(LabsSpaceEntity, SelectEntity):
    """The current experience; selecting an option pins it manually."""

    _attr_translation_key = "experience"

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "experience")

    @property
    def options(self) -> list[str]:
        return [state.name for state in self._engine.config.selectable_states]

    @property
    def current_option(self) -> str | None:
        return self._engine.active_state.name if self._engine.active_state else None

    @property
    def available(self) -> bool:
        return self._engine.enabled and self._engine.phase is not Phase.VACANT

    @property
    def icon(self) -> str | None:
        if self._engine.active_state:
            return self._engine.active_state.icon
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "state_id": self._engine.active_state.id
            if self._engine.active_state
            else None,
            "override": self._engine.override_id is not None,
            "since": self._engine.state_since,
        }

    async def async_select_option(self, option: str) -> None:
        state = self._engine.config.state_by_name(option)
        if state is None:
            raise ServiceValidationError(f"Unknown experience state: {option}")
        self._engine.async_set_override(state.id)

    async def async_set_state(self, state: str) -> None:
        """Handle the labs_experience.set_state entity service.

        Unlike selecting on the dashboard, the service wakes a vacant
        space so scripts and schedules can drive experiences directly.
        """
        target = self._engine.config.state_by_id(
            state
        ) or self._engine.config.state_by_name(state)
        if target is None:
            raise ServiceValidationError(f"Unknown experience state: {state}")
        self._engine.async_command_state(target.id)

    async def async_clear_override(self) -> None:
        """Handle the labs_experience.clear_override entity service."""
        self._engine.async_set_override(None)


class LabsLightingSelect(LabsSpaceEntity, SelectEntity):
    """Who controls the lights: the engine (auto) or a human (manual)."""

    _attr_translation_key = "lighting"
    _attr_options = [authority.value for authority in Authority]

    def __init__(self, engine: SpaceEngine) -> None:
        super().__init__(engine, "lighting")

    @property
    def current_option(self) -> str:
        return self._engine.lighting.authority.value

    @property
    def available(self) -> bool:
        return self._engine.enabled and self._engine.lighting.active

    async def async_select_option(self, option: str) -> None:
        self._engine.lighting.set_authority(Authority(option))

    async def async_set_state(self, state: str) -> None:
        raise ServiceValidationError(
            "set_state targets the Experience select, not the Lighting select"
        )

    async def async_clear_override(self) -> None:
        self._engine.lighting.set_authority(Authority.AUTO)
