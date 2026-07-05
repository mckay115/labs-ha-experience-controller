"""The presence and experience state engine that drives one space."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.script import Script
from homeassistant.util import dt as dt_util

from .const import (
    COMMAND_CYCLE_STATES,
    COMMAND_MAKE_VACANT,
    COMMAND_RESUME_AUTOMATIC,
    COMMAND_RUN_ACTIONS,
    COMMAND_SET_STATE,
    COMMAND_TOGGLE_AUTOMATION,
    COMMAND_WAKE,
    DOMAIN,
    EVENT_PASSING_THROUGH,
    EVENT_PHASE_CHANGED,
    EVENT_STATE_CHANGED,
    EVENT_TYPE,
    EVIDENCE_MODE_ANY,
    PRESENCE_ACTIVE_STATES,
    TRIGGER_ANY,
    Phase,
)
from .models import ControlBinding, ExperienceState, SpaceConfig, fallback_state

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import State

_LOGGER = logging.getLogger(__name__)


def _state_is_presence(value: str) -> bool:
    """Whether an entity state counts as someone being present.

    Numeric states cover zones and occupancy-count sensors
    (zone.backyard = "2", ESPresense/Bermuda person counts).
    """
    normalized = value.lower()
    if normalized in PRESENCE_ACTIVE_STATES:
        return True
    try:
        return float(normalized) > 0
    except ValueError:
        return False


class SpaceEngine:
    """Walks one space through its occupancy phases and experience states.

    Phases: vacant -> waking -> occupied -> cooldown -> vacant, with
    shortcuts for pass-throughs (presence that ends during waking) and
    returns (presence during cooldown). Experience states only apply
    while the space is occupied.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry_id = entry.entry_id
        self.config = SpaceConfig.from_entry(entry)
        self.phase = Phase.VACANT
        self.phase_since = dt_util.utcnow()
        self.active_state: ExperienceState | None = None
        self.state_since: datetime | None = None
        self.override_id: str | None = None
        self.enabled = True
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_track: CALLBACK_TYPE | None = None
        self._wake_cancel: CALLBACK_TYPE | None = None
        self._clear_cancel: CALLBACK_TYPE | None = None
        self._cooldown_cancel: CALLBACK_TYPE | None = None
        self._scripts: dict[str, Script | None] = {}

    # ---------------------------------------------------------------- setup

    async def async_start(self) -> None:
        """Subscribe to tracked entities and adopt the current reality.

        Adoption never replays actions, so a Home Assistant restart or
        options reload does not flash lights.
        """
        tracked = set(self.config.presence_entities)
        for state in self.config.states:
            tracked.update(state.evidence_entities)
        for control in self.config.controls:
            tracked.add(control.entity_id)
        if tracked:
            self._unsub_track = async_track_state_change_event(
                self.hass, sorted(tracked), self._handle_entity_event
            )
        if self.presence_active:
            self.phase = Phase.OCCUPIED
            self.active_state = self._infer_state()
            self.state_since = dt_util.utcnow()
        self.phase_since = dt_util.utcnow()

    @callback
    def async_stop(self) -> None:
        if self._unsub_track:
            self._unsub_track()
            self._unsub_track = None
        self._cancel_all_timers()

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Subscribe an entity to engine updates; returns an unsubscribe."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    @callback
    def _notify(self) -> None:
        for update_callback in self._listeners:
            update_callback()

    # ------------------------------------------------------------- presence

    @property
    def active_presence(self) -> list[str]:
        """Presence entities currently reporting someone here."""
        return [
            entity_id
            for entity_id in self.config.presence_entities
            if (state := self.hass.states.get(entity_id)) is not None
            and (
                _state_is_presence(state.state)
                or state.state.lower() in self.config.presence_match
            )
        ]

    @property
    def presence_active(self) -> bool:
        return bool(self.active_presence)

    @property
    def area_name(self) -> str | None:
        if not self.config.area_id:
            return None
        area = ar.async_get(self.hass).async_get_area(self.config.area_id)
        return area.name if area else None

    @property
    def _holding(self) -> bool:
        """Whether the active state keeps the space occupied without presence.

        A hold sustains occupancy (the TV is still playing) but never
        creates it — it requires evidence and only matters while occupied.
        """
        state = self.active_state
        return (
            state is not None
            and state.hold_occupancy
            and bool(state.evidence_entities)
            and self._evidence_matches(state)
        )

    @callback
    def _handle_entity_event(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        self._dispatch_controls(
            entity_id, event.data["old_state"], event.data["new_state"]
        )
        if not self.enabled:
            return
        if entity_id in self.config.presence_entities:
            self._evaluate_presence()
        if self.phase is Phase.OCCUPIED:
            self._set_experience(self._pick_state())
            self._sync_clear_timer()

    @callback
    def _evaluate_presence(self) -> None:
        if self.presence_active:
            self._cancel_clear()
            self._cancel_cooldown()
            if self.phase is Phase.VACANT:
                if self.config.wake_duration > 0:
                    self._set_phase(Phase.WAKING)
                    self._run_actions("phase_wake", self.config.wake_actions)
                    self._schedule_wake()
                else:
                    self._become_occupied()
            elif self.phase is Phase.WAKING and self._wake_cancel is None:
                # Presence returned after flickering off; resume the wake clock.
                self._schedule_wake()
            elif self.phase is Phase.COOLDOWN:
                # Someone came back before the wind-down finished; restore
                # the experience the cooldown actions interrupted.
                self._become_occupied()
        elif self.phase is Phase.WAKING:
            self._schedule_clear(self.config.pass_through_delay)
        elif self.phase is Phase.OCCUPIED:
            self._sync_clear_timer()

    @callback
    def _sync_clear_timer(self) -> None:
        """Keep the clear countdown consistent with presence and holds."""
        if self.phase is not Phase.OCCUPIED:
            return
        if self.presence_active or self._holding:
            self._cancel_clear()
        elif self._clear_cancel is None:
            self._schedule_clear(self.config.clear_delay)

    # ----------------------------------------------------------- transitions

    @callback
    def _become_occupied(self) -> None:
        self._cancel_wake()
        self._set_phase(Phase.OCCUPIED)
        self._set_experience(self._pick_state())
        self._sync_clear_timer()

    @callback
    def _go_vacant(self, *, passing: bool = False) -> None:
        self._cancel_all_timers()
        self._set_experience(None)
        self.override_id = None
        self._set_phase(Phase.VACANT)
        if passing and self.config.pass_through_actions:
            self._run_actions("phase_pass_through", self.config.pass_through_actions)
        else:
            self._run_actions("phase_vacant", self.config.vacant_actions)

    @callback
    def _set_phase(self, new_phase: Phase) -> None:
        if new_phase is self.phase:
            return
        old_phase = self.phase
        self.phase = new_phase
        self.phase_since = dt_util.utcnow()
        self._fire_event(
            EVENT_PHASE_CHANGED, {"from": old_phase.value, "to": new_phase.value}
        )
        self._notify()

    @callback
    def _set_experience(
        self, new_state: ExperienceState | None, *, run_actions: bool = True
    ) -> None:
        old_state = self.active_state
        old_id = old_state.id if old_state else None
        new_id = new_state.id if new_state else None
        if old_id == new_id:
            return
        if run_actions and old_state:
            self._run_actions(f"state_{old_state.id}_exit", old_state.exit_actions)
        self.active_state = new_state
        self.state_since = dt_util.utcnow() if new_state else None
        if run_actions and new_state:
            self._run_actions(f"state_{new_state.id}_enter", new_state.enter_actions)
        self._fire_event(
            EVENT_STATE_CHANGED,
            {
                "from": old_id,
                "from_name": old_state.name if old_state else None,
                "to": new_id,
                "to_name": new_state.name if new_state else None,
            },
        )
        self._notify()

    # ---------------------------------------------------------------- timers

    @callback
    def _schedule_wake(self) -> None:
        self._cancel_wake()
        self._wake_cancel = async_call_later(
            self.hass, self.config.wake_duration, self._wake_timer_fired
        )

    @callback
    def _schedule_clear(self, delay: int) -> None:
        self._cancel_clear()
        self._clear_cancel = async_call_later(self.hass, delay, self._clear_timer_fired)

    @callback
    def _wake_timer_fired(self, _now: datetime) -> None:
        self._wake_cancel = None
        if not self.enabled or self.phase is not Phase.WAKING:
            return
        if self.presence_active:
            self._become_occupied()

    @callback
    def _clear_timer_fired(self, _now: datetime) -> None:
        self._clear_cancel = None
        if not self.enabled or self.presence_active:
            return
        if self.phase is Phase.WAKING:
            self._fire_event(
                EVENT_PASSING_THROUGH,
                {"from": Phase.WAKING.value, "to": Phase.VACANT.value},
            )
            self._go_vacant(passing=True)
        elif self.phase is Phase.OCCUPIED:
            if self._holding:
                # Evidence is keeping the space alive (movie night with no
                # motion); the timer restarts when the hold releases.
                return
            self._set_experience(None)
            if self.config.cooldown_duration > 0:
                self._set_phase(Phase.COOLDOWN)
                self._run_actions("phase_cooldown", self.config.cooldown_actions)
                self._cooldown_cancel = async_call_later(
                    self.hass, self.config.cooldown_duration, self._cooldown_timer_fired
                )
            else:
                self._go_vacant()

    @callback
    def _cooldown_timer_fired(self, _now: datetime) -> None:
        self._cooldown_cancel = None
        if not self.enabled or self.presence_active:
            return
        if self.phase is Phase.COOLDOWN:
            self._go_vacant()

    @callback
    def _cancel_wake(self) -> None:
        if self._wake_cancel:
            self._wake_cancel()
            self._wake_cancel = None

    @callback
    def _cancel_clear(self) -> None:
        if self._clear_cancel:
            self._clear_cancel()
            self._clear_cancel = None

    @callback
    def _cancel_cooldown(self) -> None:
        if self._cooldown_cancel:
            self._cooldown_cancel()
            self._cooldown_cancel = None

    @callback
    def _cancel_all_timers(self) -> None:
        self._cancel_wake()
        self._cancel_clear()
        self._cancel_cooldown()

    # ------------------------------------------------------------- inference

    def _pick_state(self) -> ExperienceState:
        if self.override_id:
            if state := self.config.state_by_id(self.override_id):
                return state
            self.override_id = None
        return self._infer_state()

    def _infer_state(self) -> ExperienceState:
        for state in self.config.selectable_states:
            if self._evidence_matches(state):
                return state
        return fallback_state()

    def _evidence_matches(self, state: ExperienceState) -> bool:
        if not state.evidence_entities:
            return True
        results = [
            (entity_state := self.hass.states.get(entity_id)) is not None
            and entity_state.state.lower() in state.active_states
            for entity_id in state.evidence_entities
        ]
        if state.evidence_mode == EVIDENCE_MODE_ANY:
            return any(results)
        return all(results)

    # ------------------------------------------------------------- commands

    @callback
    def async_set_override(self, state_id: str | None) -> None:
        """Pin (or unpin) the experience; cleared when the space goes vacant."""
        self.override_id = state_id
        if self.phase is Phase.OCCUPIED:
            self._set_experience(self._pick_state())
            self._sync_clear_timer()
        self._notify()

    @callback
    def async_command_state(self, state_id: str) -> None:
        """Pin a state, waking the space if needed (physical controls, services)."""
        self.override_id = state_id
        if self.phase is Phase.OCCUPIED:
            self._set_experience(self._pick_state())
            self._sync_clear_timer()
        else:
            self._cancel_all_timers()
            self._become_occupied()
        self._notify()

    @callback
    def async_set_enabled(self, enabled: bool) -> None:
        """Pause or resume the engine; resuming adopts reality quietly."""
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if not enabled:
            self._cancel_all_timers()
        elif self.presence_active:
            if self.phase is not Phase.OCCUPIED:
                self.phase = Phase.OCCUPIED
                self.phase_since = dt_util.utcnow()
            self._set_experience(self._pick_state(), run_actions=False)
        elif self.phase is not Phase.VACANT:
            self._set_experience(None, run_actions=False)
            self.override_id = None
            self.phase = Phase.VACANT
            self.phase_since = dt_util.utcnow()
        self._notify()

    # -------------------------------------------------------------- controls

    @callback
    def _dispatch_controls(
        self, entity_id: str, old_state: State | None, new_state: State | None
    ) -> None:
        if new_state is None:
            return
        for control in self.config.controls:
            if control.entity_id == entity_id and self._control_triggered(
                control, old_state, new_state
            ):
                self._execute_control(control)

    def _control_triggered(
        self, control: ControlBinding, old_state: State | None, new_state: State
    ) -> bool:
        if old_state is None or old_state.state == new_state.state:
            return False
        if new_state.state in ("unknown", "unavailable"):
            return False
        if new_state.domain in ("event", "button", "input_button"):
            # These entities carry a timestamp; the pressed type (single,
            # double, long, ...) lives in the event_type attribute.
            event_type = new_state.attributes.get("event_type")
            return control.trigger == TRIGGER_ANY or control.trigger == event_type
        if control.trigger == TRIGGER_ANY:
            return True
        return new_state.state.lower() == control.trigger.lower()

    @callback
    def _execute_control(self, control: ControlBinding) -> None:
        command = control.command
        if command == COMMAND_TOGGLE_AUTOMATION:
            # Works even while paused, so a button can always un-pause.
            self.async_set_enabled(not self.enabled)
            return
        if not self.enabled:
            return
        if command == COMMAND_SET_STATE:
            if control.state_id:
                self.async_command_state(control.state_id)
        elif command == COMMAND_CYCLE_STATES:
            self._cycle_state()
        elif command == COMMAND_RESUME_AUTOMATIC:
            self.async_set_override(None)
        elif command == COMMAND_WAKE:
            self._wake_pulse()
        elif command == COMMAND_MAKE_VACANT:
            if self.phase is not Phase.VACANT:
                self._set_experience(None)
                self._go_vacant()
        elif command == COMMAND_RUN_ACTIONS:
            self._run_actions(f"control_{control.id}", control.actions)

    @callback
    def _cycle_state(self) -> None:
        states = self.config.selectable_states
        if not states:
            return
        if self.phase is not Phase.OCCUPIED:
            self.async_command_state(states[0].id)
            return
        ids = [state.id for state in states]
        current = self.active_state.id if self.active_state else None
        next_index = (ids.index(current) + 1) % len(ids) if current in ids else 0
        self.async_set_override(ids[next_index])

    @callback
    def _wake_pulse(self) -> None:
        """Acknowledge a wake command with no presence backing it yet."""
        if self.phase is not Phase.VACANT:
            return
        if self.config.wake_duration > 0:
            self._set_phase(Phase.WAKING)
            self._run_actions("phase_wake", self.config.wake_actions)
            self._schedule_wake()
            # Nobody may actually show up; treat it like a pass-through then.
            self._schedule_clear(self.config.pass_through_delay)
        else:
            self._become_occupied()

    # --------------------------------------------------------------- actions

    def _run_actions(self, key: str, sequence: list[dict[str, Any]]) -> None:
        if not sequence:
            return
        if (script := self._get_script(key, sequence)) is None:
            return
        self.hass.async_create_task(
            script.async_run(context=Context()),
            f"{DOMAIN} {self.config.name} {key}",
        )

    def _get_script(self, key: str, sequence: list[dict[str, Any]]) -> Script | None:
        if key not in self._scripts:
            try:
                validated = cv.SCRIPT_SCHEMA(sequence)
                self._scripts[key] = Script(
                    self.hass,
                    validated,
                    f"{self.config.name} {key}",
                    DOMAIN,
                    script_mode="restart",
                )
            except vol.Invalid as err:
                _LOGGER.error(
                    "Space %s has an invalid action sequence for %s: %s",
                    self.config.name,
                    key,
                    err,
                )
                self._scripts[key] = None
        return self._scripts[key]

    # ------------------------------------------------------------------ misc

    def _fire_event(self, event_subtype: str, data: dict[str, Any]) -> None:
        self.hass.bus.async_fire(
            EVENT_TYPE,
            {
                "type": event_subtype,
                "entry_id": self.entry_id,
                "space": self.config.name,
                **data,
            },
        )

    def snapshot(self) -> dict[str, Any]:
        """A diagnostic view of the engine."""
        return {
            "phase": self.phase.value,
            "phase_since": self.phase_since.isoformat(),
            "active_state": self.active_state.id if self.active_state else None,
            "state_since": self.state_since.isoformat() if self.state_since else None,
            "override": self.override_id,
            "enabled": self.enabled,
            "holding": self._holding,
            "controls": [control.id for control in self.config.controls],
            "presence": {
                entity_id: getattr(self.hass.states.get(entity_id), "state", None)
                for entity_id in self.config.presence_entities
            },
        }
