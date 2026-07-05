"""Data models for Labs Experience Controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME

from .const import (
    COMMAND_SET_STATE,
    CONF_ACTIVE_STATES,
    CONF_AREA,
    CONF_CLEAR_DELAY,
    CONF_CONTROL_ACTIONS,
    CONF_CONTROL_COMMAND,
    CONF_CONTROL_ENTITY,
    CONF_CONTROL_STATE,
    CONF_CONTROL_TRIGGER,
    CONF_CONTROLS,
    CONF_COOLDOWN_ACTIONS,
    CONF_COOLDOWN_DURATION,
    CONF_ENTER_ACTIONS,
    CONF_EVIDENCE_ENTITIES,
    CONF_EVIDENCE_MODE,
    CONF_EXIT_ACTIONS,
    CONF_HOLD_OCCUPANCY,
    CONF_PASS_THROUGH_ACTIONS,
    CONF_PASS_THROUGH_DELAY,
    CONF_PRESENCE_ENTITIES,
    CONF_PRESENCE_MATCH,
    CONF_PRIORITY,
    CONF_STATE_ICON,
    CONF_STATE_ID,
    CONF_STATE_NAME,
    CONF_STATES,
    CONF_VACANT_ACTIONS,
    CONF_WAKE_ACTIONS,
    CONF_WAKE_DURATION,
    DEFAULT_ACTIVE_STATES,
    DEFAULT_CLEAR_DELAY,
    DEFAULT_COOLDOWN_DURATION,
    DEFAULT_PASS_THROUGH_DELAY,
    DEFAULT_WAKE_DURATION,
    EVIDENCE_MODE_ANY,
    FALLBACK_STATE_ID,
    TRIGGER_ANY,
)


def parse_active_states(raw: str | list[str]) -> frozenset[str]:
    """Normalize a comma-separated string or list into a state set."""
    if isinstance(raw, str):
        raw = raw.split(",")
    return frozenset(item.strip().lower() for item in raw if item.strip())


@dataclass(slots=True)
class ExperienceState:
    """A user-defined experience state of a space."""

    id: str
    name: str
    priority: int = 0
    icon: str | None = None
    evidence_entities: list[str] = field(default_factory=list)
    evidence_mode: str = EVIDENCE_MODE_ANY
    active_states: frozenset[str] = frozenset()
    enter_actions: list[dict[str, Any]] = field(default_factory=list)
    exit_actions: list[dict[str, Any]] = field(default_factory=list)
    hold_occupancy: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceState:
        return cls(
            id=data[CONF_STATE_ID],
            name=data[CONF_STATE_NAME],
            priority=int(data.get(CONF_PRIORITY, 0)),
            icon=data.get(CONF_STATE_ICON),
            evidence_entities=list(data.get(CONF_EVIDENCE_ENTITIES, [])),
            evidence_mode=data.get(CONF_EVIDENCE_MODE, EVIDENCE_MODE_ANY),
            active_states=parse_active_states(
                data.get(CONF_ACTIVE_STATES, DEFAULT_ACTIVE_STATES)
            ),
            enter_actions=list(data.get(CONF_ENTER_ACTIONS, [])),
            exit_actions=list(data.get(CONF_EXIT_ACTIONS, [])),
            hold_occupancy=bool(data.get(CONF_HOLD_OCCUPANCY, False)),
        )


@dataclass(slots=True)
class ControlBinding:
    """A physical control (button, switch, remote) bound to a space command."""

    id: str
    entity_id: str
    trigger: str = TRIGGER_ANY
    command: str = COMMAND_SET_STATE
    state_id: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlBinding:
        return cls(
            id=data[CONF_STATE_ID],
            entity_id=data[CONF_CONTROL_ENTITY],
            trigger=data.get(CONF_CONTROL_TRIGGER, TRIGGER_ANY),
            command=data.get(CONF_CONTROL_COMMAND, COMMAND_SET_STATE),
            state_id=data.get(CONF_CONTROL_STATE),
            actions=list(data.get(CONF_CONTROL_ACTIONS, [])),
        )


def fallback_state() -> ExperienceState:
    """The implicit baseline used when no user-defined state matches."""
    return ExperienceState(id=FALLBACK_STATE_ID, name="Occupied", priority=-(10**9))


@dataclass(slots=True)
class SpaceConfig:
    """Full configuration of one space."""

    name: str
    area_id: str | None
    presence_entities: list[str]
    presence_match: frozenset[str]
    wake_duration: int
    clear_delay: int
    pass_through_delay: int
    cooldown_duration: int
    wake_actions: list[dict[str, Any]]
    cooldown_actions: list[dict[str, Any]]
    vacant_actions: list[dict[str, Any]]
    pass_through_actions: list[dict[str, Any]]
    states: list[ExperienceState]
    controls: list[ControlBinding]

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> SpaceConfig:
        options = entry.options
        return cls(
            name=entry.data.get(CONF_NAME, entry.title),
            area_id=options.get(CONF_AREA),
            presence_entities=list(options.get(CONF_PRESENCE_ENTITIES, [])),
            presence_match=parse_active_states(options.get(CONF_PRESENCE_MATCH, "")),
            wake_duration=int(options.get(CONF_WAKE_DURATION, DEFAULT_WAKE_DURATION)),
            clear_delay=int(options.get(CONF_CLEAR_DELAY, DEFAULT_CLEAR_DELAY)),
            pass_through_delay=int(
                options.get(CONF_PASS_THROUGH_DELAY, DEFAULT_PASS_THROUGH_DELAY)
            ),
            cooldown_duration=int(
                options.get(CONF_COOLDOWN_DURATION, DEFAULT_COOLDOWN_DURATION)
            ),
            wake_actions=list(options.get(CONF_WAKE_ACTIONS, [])),
            cooldown_actions=list(options.get(CONF_COOLDOWN_ACTIONS, [])),
            vacant_actions=list(options.get(CONF_VACANT_ACTIONS, [])),
            pass_through_actions=list(options.get(CONF_PASS_THROUGH_ACTIONS, [])),
            states=[ExperienceState.from_dict(s) for s in options.get(CONF_STATES, [])],
            controls=[
                ControlBinding.from_dict(c) for c in options.get(CONF_CONTROLS, [])
            ],
        )

    @property
    def has_baseline(self) -> bool:
        """Whether a user-defined state matches unconditionally."""
        return any(not state.evidence_entities for state in self.states)

    @property
    def selectable_states(self) -> list[ExperienceState]:
        """States that can become active, highest priority first."""
        states = sorted(self.states, key=lambda state: -state.priority)
        if not self.has_baseline:
            states.append(fallback_state())
        return states

    def state_by_id(self, state_id: str) -> ExperienceState | None:
        for state in self.selectable_states:
            if state.id == state_id:
                return state
        return None

    def state_by_name(self, name: str) -> ExperienceState | None:
        for state in self.selectable_states:
            if state.name == name:
                return state
        return None
