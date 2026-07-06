"""The lighting facet: circadian defaults, per-state specs, manual takeover.

Authority rule: device-level changes move this facet to `manual` and stop
the engine from touching lights — they never change the experience state.
Manual releases on vacancy, via the lighting select / resume button, or an
optional timed hold.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING

from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    callback,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .circadian import circadian_targets
from .const import (
    COLOR_KELVIN,
    COMMAND_BRIGHTEN,
    COMMAND_DIM,
    COMMAND_LIGHTS_OFF,
    COMMAND_LIGHTS_ON,
    LIGHT_COLOR_CIRCADIAN,
    LIGHT_ROLE_AMBIENT,
    LIGHT_ROLE_NIGHT,
    LUX_ADJUST_INTERVAL,
    LUX_DEADBAND,
    LUX_MAX_STEP,
    Authority,
    Daypart,
    Phase,
)
from .models import AmbianceRule, ExperienceState, LightingSpec

if TYPE_CHECKING:
    from .engine import SpaceEngine

_LOGGER = logging.getLogger(__name__)

WAKE_BRIGHTNESS = 20
COOLDOWN_BRIGHTNESS = 25
STEP_PCT = 15
UNKNOWN_STATES = ("unknown", "unavailable")


class LightingFacet:
    """Drives a space's profile lights."""

    def __init__(self, engine: SpaceEngine) -> None:
        self.engine = engine
        self.authority = Authority.AUTO
        self.circadian_enabled = engine.config.circadian_enabled
        self._current_spec: LightingSpec | None = None
        self._hold_cancel: CALLBACK_TYPE | None = None
        self._last_lux_adjust: datetime | None = None
        self._ambiance_id: str | None = None

    @property
    def active(self) -> bool:
        return self.engine.config.auto_lighting and bool(
            self.engine.config.all_profile_lights
        )

    @callback
    def cleanup(self) -> None:
        self._cancel_hold()

    # ------------------------------------------------------------- plumbing

    def _lux(self) -> float | None:
        config = self.engine.config
        if not config.illuminance_sensor:
            return None
        state = self.engine.hass.states.get(config.illuminance_sensor)
        if state is None or state.state in UNKNOWN_STATES:
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _is_dark(self) -> bool:
        """Lux gate: don't light a bright room."""
        config = self.engine.config
        if (lux := self._lux()) is not None:
            threshold = config.target_lux or config.lux_threshold
            return lux <= threshold
        # Without a sensor, assume interior spaces need light except at
        # the height of day.
        return self.engine.daypart is not Daypart.DAY

    @property
    def _lux_mode(self) -> bool:
        """Whether brightness is driven by the target-lux loop."""
        return self.engine.config.target_lux > 0 and self._lux() is not None

    def _lux_estimate(self) -> int | None:
        """Initial brightness from the measured light deficit."""
        config = self.engine.config
        lux = self._lux()
        if not config.target_lux or lux is None:
            return None
        deficit = max(0.0, min(1.0, (config.target_lux - lux) / config.target_lux))
        return round(
            config.min_brightness
            + deficit * (config.max_brightness - config.min_brightness)
        )

    def _targets(self) -> tuple[int, int]:
        config = self.engine.config
        return circadian_targets(
            self.engine.hass,
            self.engine.daypart,
            min_kelvin=config.min_kelvin,
            max_kelvin=config.max_kelvin,
            min_brightness=config.min_brightness,
            max_brightness=config.max_brightness,
        )

    def _call(self, service: str, entity_ids: list[str], data: dict | None = None) -> None:
        if not entity_ids:
            return
        context = self.engine.new_context()
        self.engine.hass.async_create_task(
            self.engine.hass.services.async_call(
                "light",
                service,
                {"entity_id": entity_ids, **(data or {})},
                context=context,
            ),
            f"labs_experience {self.engine.config.name} light.{service}",
        )

    @property
    def active_ambiance(self) -> AmbianceRule | None:
        """The highest-priority ambiance rule currently matching."""
        best: AmbianceRule | None = None
        for rule in self.engine.config.ambiance_rules:
            state = self.engine.hass.states.get(rule.entity_id)
            if state is None or state.state.lower() not in rule.states:
                continue
            if best is None or rule.priority > best.priority:
                best = rule
        return best

    def _turn_on(
        self, entity_ids: list[str], brightness: int | None, kelvin: int | None
    ) -> None:
        """Turn on lights with only the attributes each supports."""
        if brightness is not None:
            rule = self.active_ambiance
            if rule and rule.brightness_cap:
                brightness = min(brightness, rule.brightness_cap)
        for entity_id in entity_ids:
            state = self.engine.hass.states.get(entity_id)
            modes = (
                state.attributes.get("supported_color_modes") or [] if state else []
            )
            data: dict = {}
            if brightness is not None and any(mode != "onoff" for mode in modes):
                data["brightness_pct"] = brightness
            if kelvin is not None and "color_temp" in modes:
                data["color_temp_kelvin"] = kelvin
            self._call("turn_on", [entity_id], data)

    def _on_lights(self, entity_ids: list[str]) -> list[str]:
        return [
            entity_id
            for entity_id in entity_ids
            if (state := self.engine.hass.states.get(entity_id))
            and state.state == "on"
        ]

    # ----------------------------------------------------------- application

    @callback
    def apply_spec(self, spec: LightingSpec, *, turn_on: bool = True) -> None:
        if not self.active or self.authority is Authority.MANUAL:
            return
        self._current_spec = spec
        kelvin, auto_brightness = self._targets()
        if spec.brightness is not None:
            brightness = spec.brightness
        else:
            brightness = self._lux_estimate() or auto_brightness
        color_kelvin = (
            kelvin
            if spec.color == LIGHT_COLOR_CIRCADIAN
            else COLOR_KELVIN.get(spec.color)
        )
        on_lights = self.engine.config.role_lights(spec.roles)
        if turn_on:
            self._turn_on(on_lights, brightness, color_kelvin)
            if spec.exclusive:
                off_lights = [
                    entity_id
                    for entity_id in self.engine.config.all_profile_lights
                    if entity_id not in on_lights
                ]
                self._call("turn_off", off_lights)

    # ------------------------------------------------------------ engine hooks

    def _glow_roles(self) -> list[str]:
        config = self.engine.config
        if config.lights.get(LIGHT_ROLE_NIGHT):
            return [LIGHT_ROLE_NIGHT]
        return [LIGHT_ROLE_AMBIENT]

    @callback
    def on_wake(self) -> None:
        """Built-in gentle acknowledgement (no wake actions configured)."""
        if not self.active or not self._is_dark():
            return
        rule = self.active_ambiance
        brightness = (
            rule.wake_brightness
            if rule and rule.wake_brightness
            else WAKE_BRIGHTNESS
        )
        self.apply_spec(
            LightingSpec(
                roles=self._glow_roles(), brightness=brightness, exclusive=False
            )
        )

    @callback
    def on_experience(self, state: ExperienceState | None) -> None:
        if not self.active:
            return
        if state is None:
            self._current_spec = None
            return
        if state.lighting is not None:
            self.apply_spec(state.lighting, turn_on=True)
        elif not state.enter_actions:
            # Zero-config baseline: ambient on the circadian curve; only
            # turns lights on when the room is actually dark.
            self.apply_spec(
                LightingSpec(roles=[LIGHT_ROLE_AMBIENT]), turn_on=self._is_dark()
            )

    @callback
    def on_cooldown(self) -> None:
        """Built-in wind-down (no cooldown actions configured)."""
        if not self.active or self.authority is Authority.MANUAL:
            return
        self._turn_on(
            self._on_lights(self.engine.config.all_profile_lights),
            COOLDOWN_BRIGHTNESS,
            None,
        )

    @callback
    def on_vacant(self, *, actions_ran: bool) -> None:
        """Vacancy always releases manual; defaults turn the room off —
        or down to the ambiance glow when a neighbor's activity asks."""
        self.set_authority(Authority.AUTO, reapply=False)
        self._current_spec = None
        if self.active and not actions_ran:
            self._apply_vacant_default()

    @callback
    def _apply_vacant_default(self) -> None:
        config = self.engine.config
        rule = self.active_ambiance
        if rule and rule.vacant_brightness:
            glow = config.role_lights(self._glow_roles())
            self._turn_on(glow, rule.vacant_brightness, config.min_kelvin)
            self._call(
                "turn_off",
                [
                    entity_id
                    for entity_id in config.all_profile_lights
                    if entity_id not in glow
                ],
            )
        else:
            self._call("turn_off", config.all_profile_lights)

    @callback
    def on_ambiance_event(self) -> None:
        """An ambiance entity changed; re-shape the room live."""
        rule = self.active_ambiance
        rule_id = rule.id if rule else None
        if rule_id == self._ambiance_id:
            return
        self._ambiance_id = rule_id
        self.engine.async_notify()
        if not self.active or self.authority is Authority.MANUAL:
            return
        phase = self.engine.phase
        if phase is Phase.OCCUPIED and self._current_spec is not None:
            # Re-assert the current experience under the new constraints
            # (dim down for the movie, restore when it ends).
            self.apply_spec(self._current_spec)
        elif phase is Phase.VACANT and not self.engine.config.vacant_actions:
            self._apply_vacant_default()

    @callback
    def on_tick(self) -> None:
        """Periodic upkeep: circadian drift and lux compensation.

        The two are independent — a fixed-color state still gets its
        brightness held at the target lux level.
        """
        spec = self._current_spec
        if (
            not self.active
            or self.authority is Authority.MANUAL
            or self.engine.phase is not Phase.OCCUPIED
            or spec is None
        ):
            return
        if self.circadian_enabled and spec.color == LIGHT_COLOR_CIRCADIAN:
            kelvin, brightness = self._targets()
            if spec.brightness is not None or self._lux_mode:
                # Explicit or lux-driven brightness: only drift color.
                brightness = None
            self._turn_on(
                self._on_lights(self.engine.config.role_lights(spec.roles)),
                brightness,
                kelvin,
            )
        self._lux_adjust()

    # ------------------------------------------------------ lux compensation

    @callback
    def on_lux_event(self) -> None:
        """The illuminance sensor moved; nudge brightness toward target."""
        self._lux_adjust()

    @callback
    def _lux_adjust(self) -> None:
        """Closed-loop brightness: bounded, rate-limited, with a deadband
        so competing daylight never causes oscillation."""
        spec = self._current_spec
        config = self.engine.config
        if (
            not self.active
            or self.authority is Authority.MANUAL
            or self.engine.phase is not Phase.OCCUPIED
            or spec is None
            or spec.brightness is not None
            or not config.target_lux
        ):
            return
        lux = self._lux()
        if lux is None:
            return
        error = config.target_lux - lux
        if abs(error) <= LUX_DEADBAND * config.target_lux:
            return
        now = dt_util.utcnow()
        if (
            self._last_lux_adjust is not None
            and (now - self._last_lux_adjust).total_seconds() < LUX_ADJUST_INTERVAL
        ):
            return
        step = round(error / config.target_lux * 30)
        step = max(-LUX_MAX_STEP, min(LUX_MAX_STEP, step))
        if step == 0:
            return
        if step > 0 and (rule := self.active_ambiance) and rule.brightness_cap:
            # Never brighten against an ambiance cap (movie next door).
            return
        on_lights = self._on_lights(config.role_lights(spec.roles))
        if not on_lights:
            return
        self._last_lux_adjust = now
        self._call("turn_on", on_lights, {"brightness_step_pct": step})

    # -------------------------------------------------------------- takeover

    @callback
    def on_light_event(self, event: Event[EventStateChangedData]) -> None:
        if (
            not self.active
            or self.authority is Authority.MANUAL
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
        # A human touched a profile light (wall switch, app, voice):
        # they have the room now.
        self.set_authority(Authority.MANUAL)

    @callback
    def set_authority(self, authority: Authority, *, reapply: bool = True) -> None:
        if authority == self.authority:
            return
        self.authority = authority
        self._cancel_hold()
        if authority is Authority.MANUAL:
            if self.engine.config.manual_hold > 0:
                self._hold_cancel = async_call_later(
                    self.engine.hass,
                    self.engine.config.manual_hold * 60,
                    self._hold_expired,
                )
        elif (
            reapply
            and self._current_spec is not None
            and self.engine.phase is Phase.OCCUPIED
        ):
            self.apply_spec(self._current_spec)
        self.engine.fire_authority_event("lighting", authority)
        self.engine.async_notify()

    @callback
    def _hold_expired(self, _now: datetime) -> None:
        self._hold_cancel = None
        self.set_authority(Authority.AUTO)

    @callback
    def _cancel_hold(self) -> None:
        if self._hold_cancel:
            self._hold_cancel()
            self._hold_cancel = None

    # -------------------------------------------------------- control verbs

    @callback
    def command(self, verb: str) -> None:
        """Deliberate button presses: act, then hand the human the room."""
        lights = self.engine.config.all_profile_lights
        if not lights:
            return
        if verb == COMMAND_LIGHTS_ON:
            kelvin, brightness = self._targets()
            roles = (
                self._current_spec.roles
                if self._current_spec
                else [LIGHT_ROLE_AMBIENT]
            )
            targets = self.engine.config.role_lights(roles) or lights
            self._turn_on(targets, brightness, kelvin)
        elif verb == COMMAND_LIGHTS_OFF:
            self._call("turn_off", lights)
        elif verb in (COMMAND_BRIGHTEN, COMMAND_DIM):
            step = STEP_PCT if verb == COMMAND_BRIGHTEN else -STEP_PCT
            self._call(
                "turn_on", self._on_lights(lights), {"brightness_step_pct": step}
            )
        self.set_authority(Authority.MANUAL)

    def snapshot(self) -> dict:
        rule = self.active_ambiance
        return {
            "authority": self.authority.value,
            "circadian_enabled": self.circadian_enabled,
            "ambiance": rule.id if rule else None,
            "current_spec": {
                "roles": self._current_spec.roles,
                "brightness": self._current_spec.brightness,
                "color": self._current_spec.color,
            }
            if self._current_spec
            else None,
        }
