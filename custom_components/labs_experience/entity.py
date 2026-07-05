"""Base entity for Labs Experience Controller."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .engine import SpaceEngine


class LabsSpaceEntity(Entity):
    """An entity belonging to one space's device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, engine: SpaceEngine, key: str) -> None:
        self._engine = engine
        self._attr_unique_id = f"{engine.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, engine.entry_id)},
            name=engine.config.name,
            manufacturer="Labs",
            model="Space",
            suggested_area=engine.area_name,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._engine.async_add_listener(self._handle_engine_update))

    @callback
    def _handle_engine_update(self) -> None:
        self.async_write_ha_state()
