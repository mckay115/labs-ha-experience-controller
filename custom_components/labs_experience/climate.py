"""The climate facet: per-state comfort intents and window pause.

Kept deliberately conservative: it never touches thermostats unless a
state (or vacancy) declares an intent other than `keep`, and a human
adjusting a thermostat takes the facet manual until the space is vacant.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    CLIMATE_INTENT_COMFORT,
    CLIMATE_INTENT_ECO,
    CLIMATE_INTENT_KEEP,
    CLIMATE_INTENT_OFF,
    Authority,
    Phase,
)
from .models import ExperienceState

if TYPE_CHECKING:
    from .engine import SpaceEngine

_LOGGER = logging.getLogger(__name__)

UNKNOWN_STATES = ("unknown", "unavailable")
OPEN_STATES = ("on", "open")


class ClimateFacet:
    """Occupancy-aware comfort management for a space."""

    def __init__(self, engine: SpaceEngine) -> None:
        self.engine = engine
        self.authority = Authority.AUTO
        self.window_paused = False
        self._saved: dict[str, dict[str, Any]] = {}
        self._window_cancel: CALLBACK_TYPE | None = None

    @property
    def active(self) -> bool:
        return bool(self.engine.config.climate_entities)

    @callback
    def cleanup(self) -> None:
        self._cancel_window_timer()

    def _call(self, service: str, entity_ids: list[str], data: dict | None = None) -> None:
        if not entity_ids:
            return
        context = self.engine.new_context()
        self.engine.hass.async_create_task(
            self.engine.hass.services.async_call(
                "climate",
                service,
                {"entity_id": entity_ids, **(data or {})},
                context=context,
            ),
            f"labs_experience {self.engine.config.name} climate.{service}",
        )

    def _apply_intent(self, intent: str) -> None:
        if (
            not self.active
            or intent == CLIMATE_INTENT_KEEP
            or self.authority is Authority.MANUAL
            or self.window_paused
        ):
            return
        entities = self.engine.config.climate_entities
        if intent == CLIMATE_INTENT_COMFORT:
            self._call(
                "set_temperature",
                entities,
                {"temperature": self.engine.config.comfort_temp},
            )
        elif intent == CLIMATE_INTENT_ECO:
            self._call(
                "set_temperature",
                entities,
                {"temperature": self.engine.config.eco_temp},
            )
        elif intent == CLIMATE_INTENT_OFF:
            self._call("turn_off", entities)

    # ------------------------------------------------------------ engine hooks

    @callback
    def on_experience(self, state: ExperienceState | None) -> None:
        if state is not None:
            self._apply_intent(state.climate_intent)

    @callback
    def on_vacant(self) -> None:
        self.authority = Authority.AUTO
        self._apply_intent(self.engine.config.vacant_climate)

    # ------------------------------------------------------------ window pause

    def _any_window_open(self) -> bool:
        return any(
            (state := self.engine.hass.states.get(entity_id)) is not None
            and state.state in OPEN_STATES
            for entity_id in self.engine.config.window_sensors
        )

    @callback
    def on_window_event(self, _event: Event[EventStateChangedData]) -> None:
        if not self.active:
            return
        if self._any_window_open():
            if not self.window_paused and self._window_cancel is None:
                self._window_cancel = async_call_later(
                    self.engine.hass,
                    self.engine.config.window_pause_delay,
                    self._window_open_confirmed,
                )
        else:
            self._cancel_window_timer()
            if self.window_paused:
                self._resume_from_window()

    @callback
    def _window_open_confirmed(self, _now: datetime) -> None:
        self._window_cancel = None
        if not self._any_window_open() or self.window_paused:
            return
        self.window_paused = True
        for entity_id in self.engine.config.climate_entities:
            state = self.engine.hass.states.get(entity_id)
            if state is not None and state.state not in UNKNOWN_STATES:
                self._saved[entity_id] = {
                    "hvac_mode": state.state,
                    "temperature": state.attributes.get("temperature"),
                }
        self._call("turn_off", self.engine.config.climate_entities)
        self.engine.fire_facet_event("climate", "window_pause")
        self.engine.async_notify()

    @callback
    def _resume_from_window(self) -> None:
        self.window_paused = False
        for entity_id, saved in self._saved.items():
            hvac_mode = saved.get("hvac_mode")
            if hvac_mode and hvac_mode != "off":
                self._call("set_hvac_mode", [entity_id], {"hvac_mode": hvac_mode})
                if saved.get("temperature") is not None:
                    self._call(
                        "set_temperature",
                        [entity_id],
                        {"temperature": saved["temperature"]},
                    )
        self._saved = {}
        self.engine.fire_facet_event("climate", "window_resume")
        self.engine.async_notify()

    @callback
    def _cancel_window_timer(self) -> None:
        if self._window_cancel:
            self._window_cancel()
            self._window_cancel = None

    # -------------------------------------------------------------- takeover

    @callback
    def on_climate_event(self, event: Event[EventStateChangedData]) -> None:
        if (
            not self.active
            or self.authority is Authority.MANUAL
            or self.window_paused
            or self.engine.phase not in (Phase.WAKING, Phase.OCCUPIED)
        ):
            return
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        if (
            old_state is None
            or new_state is None
            or old_state.state in UNKNOWN_STATES
            or new_state.state in UNKNOWN_STATES
        ):
            return
        if self.engine.is_own_context(event.context):
            return
        # Only *control* changes count — hvac mode or target temperature.
        # Current-temperature drift reports constantly and is not a human.
        if new_state.state != old_state.state or new_state.attributes.get(
            "temperature"
        ) != old_state.attributes.get("temperature"):
            self.set_authority(Authority.MANUAL)

    @callback
    def set_authority(self, authority: Authority) -> None:
        if authority == self.authority:
            return
        self.authority = authority
        self.engine.fire_authority_event("climate", authority)
        self.engine.async_notify()

    def snapshot(self) -> dict[str, Any]:
        return {
            "authority": self.authority.value,
            "window_paused": self.window_paused,
        }
