"""Data models for Labs Experience Controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME

from .const import (
    CLIMATE_INTENT_KEEP,
    COMMAND_SET_STATE,
    CONF_ACTIVE_STATES,
    CONF_AMBIANCE_ENTITY,
    CONF_AMBIANCE_RULES,
    CONF_AMBIANCE_STATES,
    CONF_APPLIANCE_ENTITIES,
    CONF_AREA,
    CONF_AUTO_LIGHTING,
    CONF_BRIGHTNESS_CAP,
    CONF_CIRCADIAN,
    CONF_CLEAR_DELAY,
    CONF_CLIMATE_ENTITIES,
    CONF_CLIMATE_INTENT,
    CONF_COMFORT_TEMP,
    CONF_CONTROL_ACTIONS,
    CONF_CONTROL_COMMAND,
    CONF_CONTROL_ENTITY,
    CONF_CONTROL_EVENT_DATA,
    CONF_CONTROL_EVENT_TYPE,
    CONF_CONTROL_KIND,
    CONF_CONTROL_STATE,
    CONF_CONTROL_TRIGGER,
    CONF_CONTROLS,
    CONF_COOLDOWN_ACTIONS,
    CONF_COOLDOWN_DURATION,
    CONF_DAY_START,
    CONF_DAYPARTS,
    CONF_DOOR_SENSORS,
    CONF_ECO_TEMP,
    CONF_ENTER_ACTIONS,
    CONF_EVENING_START,
    CONF_EVIDENCE_ENTITIES,
    CONF_EVIDENCE_MODE,
    CONF_EXIT_ACTIONS,
    CONF_HOLD_OCCUPANCY,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_BRIGHTNESS,
    CONF_LIGHT_COLOR,
    CONF_LIGHT_EXCLUSIVE,
    CONF_LIGHT_ROLES,
    CONF_LUX_THRESHOLD,
    CONF_MANUAL_HOLD,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_KELVIN,
    CONF_MEDIA_ENTITIES,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_KELVIN,
    CONF_MORNING_START,
    CONF_NIGHT_START,
    CONF_PASS_THROUGH_ACTIONS,
    CONF_PASS_THROUGH_DELAY,
    CONF_PRESENCE_ENTITIES,
    CONF_PRESENCE_MATCH,
    CONF_PRIORITY,
    CONF_STATE_ICON,
    CONF_STATE_ID,
    CONF_STATE_NAME,
    CONF_STATES,
    CONF_TARGET_LUX,
    CONF_VACANT_ACTIONS,
    CONF_VACANT_BRIGHTNESS,
    CONF_VACANT_CLIMATE,
    CONF_WAKE_ACTIONS,
    CONF_WAKE_BRIGHTNESS,
    CONF_WAKE_DURATION,
    CONF_WINDOW_PAUSE_DELAY,
    CONF_WINDOW_SENSORS,
    CONTROL_KIND_ENTITY,
    DEFAULT_ACTIVE_STATES,
    DEFAULT_CLEAR_DELAY,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_COOLDOWN_DURATION,
    DEFAULT_DAY_START,
    DEFAULT_ECO_TEMP,
    DEFAULT_EVENING_START,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_MANUAL_HOLD,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_MIN_KELVIN,
    DEFAULT_MORNING_START,
    DEFAULT_NIGHT_START,
    DEFAULT_PASS_THROUGH_DELAY,
    DEFAULT_TARGET_LUX,
    DEFAULT_VACANT_CLIMATE,
    DEFAULT_WAKE_DURATION,
    DEFAULT_WINDOW_PAUSE_DELAY,
    EVIDENCE_MODE_ANY,
    FALLBACK_STATE_ID,
    LIGHT_COLOR_CIRCADIAN,
    LIGHT_ROLE_KEYS,
    TRIGGER_ANY,
)


def parse_active_states(raw: str | list[str]) -> frozenset[str]:
    """Normalize a comma-separated string or list into a state set."""
    if isinstance(raw, str):
        raw = raw.split(",")
    return frozenset(item.strip().lower() for item in raw if item.strip())


@dataclass(slots=True)
class LightingSpec:
    """Declarative lighting for an experience state."""

    roles: list[str]
    brightness: int | None = None
    color: str = LIGHT_COLOR_CIRCADIAN
    exclusive: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LightingSpec | None:
        roles = list(data.get(CONF_LIGHT_ROLES, []))
        if not roles:
            return None
        brightness = data.get(CONF_LIGHT_BRIGHTNESS)
        return cls(
            roles=roles,
            brightness=int(brightness) if brightness is not None else None,
            color=data.get(CONF_LIGHT_COLOR, LIGHT_COLOR_CIRCADIAN),
            exclusive=bool(data.get(CONF_LIGHT_EXCLUSIVE, True)),
        )


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
    dayparts: list[str] = field(default_factory=list)
    lighting: LightingSpec | None = None
    climate_intent: str = CLIMATE_INTENT_KEEP

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
            dayparts=list(data.get(CONF_DAYPARTS, [])),
            lighting=LightingSpec.from_dict(data),
            climate_intent=data.get(CONF_CLIMATE_INTENT, CLIMATE_INTENT_KEEP),
        )


@dataclass(slots=True)
class ControlBinding:
    """A physical control (button, switch, remote) bound to a space command.

    Two kinds: `entity` bindings watch an entity's state/event-type,
    `bus_event` bindings match raw bus events (zha_event, hue_event, ...)
    fired by remotes that never become entities.
    """

    id: str
    kind: str = CONTROL_KIND_ENTITY
    entity_id: str | None = None
    trigger: str = TRIGGER_ANY
    event_type: str | None = None
    event_data: dict[str, Any] = field(default_factory=dict)
    command: str = COMMAND_SET_STATE
    state_id: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    dayparts: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlBinding:
        return cls(
            id=data[CONF_STATE_ID],
            kind=data.get(CONF_CONTROL_KIND, CONTROL_KIND_ENTITY),
            entity_id=data.get(CONF_CONTROL_ENTITY),
            trigger=data.get(CONF_CONTROL_TRIGGER, TRIGGER_ANY),
            event_type=data.get(CONF_CONTROL_EVENT_TYPE),
            event_data=dict(data.get(CONF_CONTROL_EVENT_DATA, {})),
            command=data.get(CONF_CONTROL_COMMAND, COMMAND_SET_STATE),
            state_id=data.get(CONF_CONTROL_STATE),
            actions=list(data.get(CONF_CONTROL_ACTIONS, [])),
            dayparts=list(data.get(CONF_DAYPARTS, [])),
        )


@dataclass(slots=True)
class AmbianceRule:
    """A lighting overlay driven by another entity's state.

    Typically the entity is a neighbor space's experience select, making
    this space a *passive* participant in the neighbor's activity —
    dimmed while the living-room movie runs, glowing instead of dark
    when idle.
    """

    id: str
    entity_id: str
    states: frozenset[str]
    priority: int = 0
    brightness_cap: int | None = None
    vacant_brightness: int | None = None
    wake_brightness: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AmbianceRule:
        def opt_int(value: Any) -> int | None:
            return int(value) if value is not None else None

        return cls(
            id=data[CONF_STATE_ID],
            entity_id=data[CONF_AMBIANCE_ENTITY],
            states=parse_active_states(data.get(CONF_AMBIANCE_STATES, "")),
            priority=int(data.get(CONF_PRIORITY, 0)),
            brightness_cap=opt_int(data.get(CONF_BRIGHTNESS_CAP)),
            vacant_brightness=opt_int(data.get(CONF_VACANT_BRIGHTNESS)),
            wake_brightness=opt_int(data.get(CONF_WAKE_BRIGHTNESS)),
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
    ambiance_rules: list[AmbianceRule]
    # Room profile
    lights: dict[str, list[str]]
    climate_entities: list[str]
    window_sensors: list[str]
    door_sensors: list[str]
    media_entities: list[str]
    appliance_entities: list[str]
    illuminance_sensor: str | None
    lux_threshold: float
    target_lux: float
    # Lighting facet
    auto_lighting: bool
    circadian_enabled: bool
    min_kelvin: int
    max_kelvin: int
    min_brightness: int
    max_brightness: int
    manual_hold: int
    # Climate facet
    comfort_temp: float
    eco_temp: float
    vacant_climate: str
    window_pause_delay: int
    # Daypart boundaries ("HH:MM")
    morning_start: str
    day_start: str
    evening_start: str
    night_start: str

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
            ambiance_rules=[
                AmbianceRule.from_dict(r)
                for r in options.get(CONF_AMBIANCE_RULES, [])
            ],
            lights={
                role: list(options.get(key, []))
                for role, key in LIGHT_ROLE_KEYS.items()
            },
            climate_entities=list(options.get(CONF_CLIMATE_ENTITIES, [])),
            window_sensors=list(options.get(CONF_WINDOW_SENSORS, [])),
            door_sensors=list(options.get(CONF_DOOR_SENSORS, [])),
            media_entities=list(options.get(CONF_MEDIA_ENTITIES, [])),
            appliance_entities=list(options.get(CONF_APPLIANCE_ENTITIES, [])),
            illuminance_sensor=options.get(CONF_ILLUMINANCE_SENSOR),
            lux_threshold=float(
                options.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD)
            ),
            target_lux=float(options.get(CONF_TARGET_LUX, DEFAULT_TARGET_LUX)),
            auto_lighting=bool(options.get(CONF_AUTO_LIGHTING, True)),
            circadian_enabled=bool(options.get(CONF_CIRCADIAN, True)),
            min_kelvin=int(options.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN)),
            max_kelvin=int(options.get(CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN)),
            min_brightness=int(
                options.get(CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS)
            ),
            max_brightness=int(
                options.get(CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS)
            ),
            manual_hold=int(options.get(CONF_MANUAL_HOLD, DEFAULT_MANUAL_HOLD)),
            comfort_temp=float(options.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)),
            eco_temp=float(options.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP)),
            vacant_climate=options.get(CONF_VACANT_CLIMATE, DEFAULT_VACANT_CLIMATE),
            window_pause_delay=int(
                options.get(CONF_WINDOW_PAUSE_DELAY, DEFAULT_WINDOW_PAUSE_DELAY)
            ),
            morning_start=options.get(CONF_MORNING_START, DEFAULT_MORNING_START),
            day_start=options.get(CONF_DAY_START, DEFAULT_DAY_START),
            evening_start=options.get(CONF_EVENING_START, DEFAULT_EVENING_START),
            night_start=options.get(CONF_NIGHT_START, DEFAULT_NIGHT_START),
        )

    @property
    def all_profile_lights(self) -> list[str]:
        seen: dict[str, None] = {}
        for entities in self.lights.values():
            for entity_id in entities:
                seen[entity_id] = None
        return list(seen)

    def role_lights(self, roles: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for role in roles:
            for entity_id in self.lights.get(role, []):
                seen[entity_id] = None
        return list(seen)

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
