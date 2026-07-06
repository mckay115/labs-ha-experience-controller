"""Config and options flows for Labs Experience Controller."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.selector import selector
from homeassistant.util import slugify
import voluptuous as vol

from .const import (
    CLIMATE_INTENT_KEEP,
    CLIMATE_INTENTS,
    COMMAND_SET_STATE,
    COMMAND_TOGGLE_STATE,
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
    CONF_LIGHTS_ACCENT,
    CONF_LIGHTS_AMBIENT,
    CONF_LIGHTS_NIGHT,
    CONF_LIGHTS_TASK,
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
    CONTROL_CAPTURE_TIMEOUT,
    CONTROL_COMMANDS,
    CONTROL_KIND_BUS,
    CONTROL_KIND_ENTITY,
    CONTROLLER_EVENT_TYPES,
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
    DOMAIN,
    EVIDENCE_MODE_ANY,
    LIGHT_COLOR_CIRCADIAN,
    TRIGGER_ANY,
    Daypart,
)
from .state_form import flatten_state_input, state_schema

PRESENCE_DOMAINS = [
    "binary_sensor",
    "input_boolean",
    "device_tracker",
    "person",
    "zone",
    "sensor",
    "switch",
]

CONTROL_DOMAINS = [
    "event",
    "binary_sensor",
    "switch",
    "sensor",
    "button",
    "input_button",
    "input_boolean",
    "select",
    "input_select",
]

DURATION_KEYS = (
    CONF_WAKE_DURATION,
    CONF_CLEAR_DELAY,
    CONF_PASS_THROUGH_DELAY,
    CONF_COOLDOWN_DURATION,
)

DURATION_DEFAULTS = {
    CONF_WAKE_DURATION: DEFAULT_WAKE_DURATION,
    CONF_CLEAR_DELAY: DEFAULT_CLEAR_DELAY,
    CONF_PASS_THROUGH_DELAY: DEFAULT_PASS_THROUGH_DELAY,
    CONF_COOLDOWN_DURATION: DEFAULT_COOLDOWN_DURATION,
}


def _duration_selector() -> Any:
    return selector(
        {
            "number": {
                "min": 0,
                "max": 86400,
                "step": 1,
                "unit_of_measurement": "s",
                "mode": "box",
            }
        }
    )


def _basics_schema(defaults: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Optional(
            CONF_AREA, description={"suggested_value": defaults.get(CONF_AREA)}
        ): selector({"area": {}}),
        vol.Required(
            CONF_PRESENCE_ENTITIES,
            default=list(defaults.get(CONF_PRESENCE_ENTITIES, [])),
        ): selector(
            {"entity": {"multiple": True, "filter": [{"domain": PRESENCE_DOMAINS}]}}
        ),
        vol.Optional(
            CONF_PRESENCE_MATCH, default=defaults.get(CONF_PRESENCE_MATCH, "")
        ): selector({"text": {}}),
    }
    for key in DURATION_KEYS:
        schema[
            vol.Required(key, default=int(defaults.get(key, DURATION_DEFAULTS[key])))
        ] = _duration_selector()
    return vol.Schema(schema)


def _normalize_basics(user_input: dict[str, Any]) -> dict[str, Any]:
    result = dict(user_input)
    for key in DURATION_KEYS:
        if key in result:
            result[key] = int(result[key])
    return result


LIGHT_ROLE_CONF_KEYS = [
    CONF_LIGHTS_AMBIENT,
    CONF_LIGHTS_TASK,
    CONF_LIGHTS_ACCENT,
    CONF_LIGHTS_NIGHT,
]

PROFILE_LIST_KEYS = [
    *LIGHT_ROLE_CONF_KEYS,
    CONF_CLIMATE_ENTITIES,
    CONF_WINDOW_SENSORS,
    CONF_DOOR_SENSORS,
    CONF_MEDIA_ENTITIES,
    CONF_APPLIANCE_ENTITIES,
]

PROFILE_DOMAIN_FILTERS = {
    CONF_LIGHTS_AMBIENT: ["light"],
    CONF_LIGHTS_TASK: ["light"],
    CONF_LIGHTS_ACCENT: ["light"],
    CONF_LIGHTS_NIGHT: ["light"],
    CONF_CLIMATE_ENTITIES: ["climate"],
    CONF_WINDOW_SENSORS: ["binary_sensor"],
    CONF_DOOR_SENSORS: ["binary_sensor"],
    CONF_MEDIA_ENTITIES: ["media_player"],
    CONF_APPLIANCE_ENTITIES: ["switch", "binary_sensor", "sensor", "fan", "vacuum"],
}


def _profile_schema(defaults: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {}
    for key in PROFILE_LIST_KEYS:
        schema[vol.Optional(key, default=list(defaults.get(key, [])))] = selector(
            {
                "entity": {
                    "multiple": True,
                    "filter": [{"domain": PROFILE_DOMAIN_FILTERS[key]}],
                }
            }
        )
    schema[
        vol.Optional(
            CONF_ILLUMINANCE_SENSOR,
            description={"suggested_value": defaults.get(CONF_ILLUMINANCE_SENSOR)},
        )
    ] = selector(
        {"entity": {"filter": [{"domain": ["sensor"], "device_class": ["illuminance"]}]}}
    )
    schema[
        vol.Required(
            CONF_LUX_THRESHOLD,
            default=float(defaults.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD)),
        )
    ] = selector(
        {"number": {"min": 0, "max": 10000, "step": 1, "unit_of_measurement": "lx", "mode": "box"}}
    )
    schema[
        vol.Required(
            CONF_TARGET_LUX,
            default=float(defaults.get(CONF_TARGET_LUX, DEFAULT_TARGET_LUX)),
        )
    ] = selector(
        {"number": {"min": 0, "max": 2000, "step": 10, "unit_of_measurement": "lx", "mode": "box"}}
    )
    return vol.Schema(schema)


def _lighting_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_AUTO_LIGHTING,
                default=bool(defaults.get(CONF_AUTO_LIGHTING, True)),
            ): selector({"boolean": {}}),
            vol.Required(
                CONF_CIRCADIAN, default=bool(defaults.get(CONF_CIRCADIAN, True))
            ): selector({"boolean": {}}),
            vol.Required(
                CONF_MIN_KELVIN,
                default=int(defaults.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN)),
            ): selector(
                {"number": {"min": 1000, "max": 10000, "step": 50, "unit_of_measurement": "K", "mode": "box"}}
            ),
            vol.Required(
                CONF_MAX_KELVIN,
                default=int(defaults.get(CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN)),
            ): selector(
                {"number": {"min": 1000, "max": 10000, "step": 50, "unit_of_measurement": "K", "mode": "box"}}
            ),
            vol.Required(
                CONF_MIN_BRIGHTNESS,
                default=int(defaults.get(CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS)),
            ): selector(
                {"number": {"min": 1, "max": 100, "unit_of_measurement": "%", "mode": "box"}}
            ),
            vol.Required(
                CONF_MAX_BRIGHTNESS,
                default=int(defaults.get(CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS)),
            ): selector(
                {"number": {"min": 1, "max": 100, "unit_of_measurement": "%", "mode": "box"}}
            ),
            vol.Required(
                CONF_MANUAL_HOLD,
                default=int(defaults.get(CONF_MANUAL_HOLD, DEFAULT_MANUAL_HOLD)),
            ): selector(
                {"number": {"min": 0, "max": 720, "unit_of_measurement": "min", "mode": "box"}}
            ),
            vol.Required(
                CONF_MORNING_START,
                default=defaults.get(CONF_MORNING_START, DEFAULT_MORNING_START),
            ): selector({"time": {}}),
            vol.Required(
                CONF_DAY_START,
                default=defaults.get(CONF_DAY_START, DEFAULT_DAY_START),
            ): selector({"time": {}}),
            vol.Required(
                CONF_EVENING_START,
                default=defaults.get(CONF_EVENING_START, DEFAULT_EVENING_START),
            ): selector({"time": {}}),
            vol.Required(
                CONF_NIGHT_START,
                default=defaults.get(CONF_NIGHT_START, DEFAULT_NIGHT_START),
            ): selector({"time": {}}),
        }
    )


def _climate_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_COMFORT_TEMP,
                default=float(defaults.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)),
            ): selector(
                {"number": {"min": 5, "max": 35, "step": 0.5, "unit_of_measurement": "°", "mode": "box"}}
            ),
            vol.Required(
                CONF_ECO_TEMP,
                default=float(defaults.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP)),
            ): selector(
                {"number": {"min": 5, "max": 35, "step": 0.5, "unit_of_measurement": "°", "mode": "box"}}
            ),
            vol.Required(
                CONF_VACANT_CLIMATE,
                default=defaults.get(CONF_VACANT_CLIMATE, DEFAULT_VACANT_CLIMATE),
            ): selector(
                {"select": {"options": list(CLIMATE_INTENTS), "translation_key": "climate_intent"}}
            ),
            vol.Required(
                CONF_WINDOW_PAUSE_DELAY,
                default=int(
                    defaults.get(CONF_WINDOW_PAUSE_DELAY, DEFAULT_WINDOW_PAUSE_DELAY)
                ),
            ): selector(
                {"number": {"min": 0, "max": 3600, "unit_of_measurement": "s", "mode": "box"}}
            ),
        }
    )


def _ambiance_schema(defaults: dict[str, Any]) -> vol.Schema:
    def opt_pct(key: str) -> Any:
        return vol.Optional(key, description={"suggested_value": defaults.get(key)})

    pct = selector(
        {"number": {"min": 1, "max": 100, "unit_of_measurement": "%", "mode": "box"}}
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_AMBIANCE_ENTITY,
                description={"suggested_value": defaults.get(CONF_AMBIANCE_ENTITY)},
            ): selector({"entity": {}}),
            vol.Required(
                CONF_AMBIANCE_STATES,
                default=defaults.get(CONF_AMBIANCE_STATES, "media"),
            ): selector({"text": {}}),
            vol.Required(
                CONF_PRIORITY, default=int(defaults.get(CONF_PRIORITY, 0))
            ): selector(
                {"number": {"min": -1000, "max": 1000, "step": 1, "mode": "box"}}
            ),
            opt_pct(CONF_BRIGHTNESS_CAP): pct,
            opt_pct(CONF_VACANT_BRIGHTNESS): pct,
            opt_pct(CONF_WAKE_BRIGHTNESS): pct,
        }
    )


def _ambiance_from_input(user_input: dict[str, Any], rule_id: str) -> dict[str, Any]:
    def opt_int(key: str) -> int | None:
        value = user_input.get(key)
        return int(value) if value is not None else None

    return {
        CONF_STATE_ID: rule_id,
        CONF_AMBIANCE_ENTITY: user_input[CONF_AMBIANCE_ENTITY],
        CONF_AMBIANCE_STATES: user_input.get(CONF_AMBIANCE_STATES, "media"),
        CONF_PRIORITY: int(user_input.get(CONF_PRIORITY, 0)),
        CONF_BRIGHTNESS_CAP: opt_int(CONF_BRIGHTNESS_CAP),
        CONF_VACANT_BRIGHTNESS: opt_int(CONF_VACANT_BRIGHTNESS),
        CONF_WAKE_BRIGHTNESS: opt_int(CONF_WAKE_BRIGHTNESS),
    }


def _ambiance_label(rule: dict[str, Any]) -> str:
    parts = []
    if rule.get(CONF_BRIGHTNESS_CAP):
        parts.append(f"cap {rule[CONF_BRIGHTNESS_CAP]}%")
    if rule.get(CONF_VACANT_BRIGHTNESS):
        parts.append(f"glow {rule[CONF_VACANT_BRIGHTNESS]}%")
    if rule.get(CONF_WAKE_BRIGHTNESS):
        parts.append(f"wake {rule[CONF_WAKE_BRIGHTNESS]}%")
    effect = ", ".join(parts) or "no effect"
    return (
        f"{rule.get(CONF_AMBIANCE_ENTITY)} = "
        f"{rule.get(CONF_AMBIANCE_STATES)} → {effect}"
    )


STARTER_HANGING_OUT = "hanging_out"
STARTER_MEDIA = "media"
STARTER_WORKING = "working"
STARTER_NIGHT_LIGHT = "night_light"
STARTER_TEMPLATES = [
    STARTER_HANGING_OUT,
    STARTER_MEDIA,
    STARTER_WORKING,
    STARTER_NIGHT_LIGHT,
]


def _starter_states(
    selected: list[str], media_entity: str | None, work_entity: str | None
) -> list[dict[str, Any]]:
    """Pre-tuned experience states so a fresh space is smart in one visit."""
    states: list[dict[str, Any]] = []
    if STARTER_HANGING_OUT in selected:
        states.append(
            {
                CONF_STATE_ID: STARTER_HANGING_OUT,
                CONF_STATE_NAME: "Hanging out",
                CONF_STATE_ICON: "mdi:sofa",
                CONF_PRIORITY: 0,
                CONF_LIGHT_ROLES: ["ambient"],
                CONF_LIGHT_COLOR: LIGHT_COLOR_CIRCADIAN,
            }
        )
    if STARTER_MEDIA in selected:
        states.append(
            {
                CONF_STATE_ID: STARTER_MEDIA,
                CONF_STATE_NAME: "Media",
                CONF_STATE_ICON: "mdi:television-play",
                CONF_PRIORITY: 20,
                CONF_EVIDENCE_ENTITIES: [media_entity],
                CONF_ACTIVE_STATES: "playing,buffering",
                CONF_HOLD_OCCUPANCY: True,
                CONF_LIGHT_ROLES: ["ambient"],
                CONF_LIGHT_BRIGHTNESS: 20,
                CONF_LIGHT_COLOR: "warm",
            }
        )
    if STARTER_WORKING in selected:
        states.append(
            {
                CONF_STATE_ID: STARTER_WORKING,
                CONF_STATE_NAME: "Working",
                CONF_STATE_ICON: "mdi:desk",
                CONF_PRIORITY: 10,
                CONF_EVIDENCE_ENTITIES: [work_entity],
                CONF_LIGHT_ROLES: ["ambient", "task"],
                CONF_LIGHT_BRIGHTNESS: 100,
                CONF_LIGHT_COLOR: "cool",
            }
        )
    if STARTER_NIGHT_LIGHT in selected:
        states.append(
            {
                CONF_STATE_ID: STARTER_NIGHT_LIGHT,
                CONF_STATE_NAME: "Night light",
                CONF_STATE_ICON: "mdi:weather-night",
                CONF_PRIORITY: 5,
                CONF_DAYPARTS: ["night"],
                CONF_LIGHT_ROLES: ["night"],
                CONF_LIGHT_BRIGHTNESS: 10,
                CONF_LIGHT_COLOR: "warm",
            }
        )
    return states


def _classify_area(hass: HomeAssistant, area_id: str) -> dict[str, Any]:
    """Build profile assignments from an area's entities."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entries = {
        entry.entity_id: entry
        for entry in er.async_entries_for_area(ent_reg, area_id)
    }
    for device in dr.async_entries_for_area(dev_reg, area_id):
        for entry in er.async_entries_for_device(ent_reg, device.id):
            if entry.area_id is None:
                entries.setdefault(entry.entity_id, entry)

    filled: dict[str, list[str]] = {
        CONF_PRESENCE_ENTITIES: [],
        CONF_LIGHTS_AMBIENT: [],
        CONF_CLIMATE_ENTITIES: [],
        CONF_MEDIA_ENTITIES: [],
        CONF_WINDOW_SENSORS: [],
        CONF_DOOR_SENSORS: [],
    }
    illuminance: str | None = None
    for entity_id, entry in sorted(entries.items()):
        if entry.disabled_by or entry.hidden_by or entry.entity_category:
            continue
        domain = entity_id.split(".", 1)[0]
        state = hass.states.get(entity_id)
        device_class = (state and state.attributes.get("device_class")) or (
            entry.device_class or entry.original_device_class
        )
        if domain == "light":
            filled[CONF_LIGHTS_AMBIENT].append(entity_id)
        elif domain == "climate":
            filled[CONF_CLIMATE_ENTITIES].append(entity_id)
        elif domain == "media_player":
            filled[CONF_MEDIA_ENTITIES].append(entity_id)
        elif domain == "binary_sensor":
            if device_class in ("motion", "occupancy", "presence"):
                filled[CONF_PRESENCE_ENTITIES].append(entity_id)
            elif device_class == "window":
                filled[CONF_WINDOW_SENSORS].append(entity_id)
            elif device_class in ("door", "garage_door", "opening"):
                filled[CONF_DOOR_SENSORS].append(entity_id)
        elif domain == "sensor" and device_class == "illuminance":
            illuminance = illuminance or entity_id
    result: dict[str, Any] = {key: value for key, value in filled.items() if value}
    if illuminance:
        result[CONF_ILLUMINANCE_SENSOR] = illuminance
    return result


def _state_schema(defaults: dict[str, Any]) -> vol.Schema:
    return state_schema(defaults)


def _state_from_input(user_input: dict[str, Any], state_id: str) -> dict[str, Any]:
    return {
        CONF_STATE_ID: state_id,
        CONF_STATE_NAME: user_input[CONF_STATE_NAME],
        CONF_STATE_ICON: user_input.get(CONF_STATE_ICON),
        CONF_PRIORITY: int(user_input.get(CONF_PRIORITY, 0)),
        CONF_EVIDENCE_ENTITIES: list(user_input.get(CONF_EVIDENCE_ENTITIES, [])),
        CONF_EVIDENCE_MODE: user_input.get(CONF_EVIDENCE_MODE, EVIDENCE_MODE_ANY),
        CONF_ACTIVE_STATES: user_input.get(CONF_ACTIVE_STATES, DEFAULT_ACTIVE_STATES),
        CONF_HOLD_OCCUPANCY: bool(user_input.get(CONF_HOLD_OCCUPANCY, False)),
        CONF_DAYPARTS: list(user_input.get(CONF_DAYPARTS, [])),
        CONF_LIGHT_ROLES: list(user_input.get(CONF_LIGHT_ROLES, [])),
        CONF_LIGHT_BRIGHTNESS: int(brightness)
        if (brightness := user_input.get(CONF_LIGHT_BRIGHTNESS)) is not None
        else None,
        CONF_LIGHT_COLOR: user_input.get(CONF_LIGHT_COLOR, LIGHT_COLOR_CIRCADIAN),
        CONF_LIGHT_EXCLUSIVE: bool(user_input.get(CONF_LIGHT_EXCLUSIVE, True)),
        CONF_CLIMATE_INTENT: user_input.get(CONF_CLIMATE_INTENT, CLIMATE_INTENT_KEEP),
        CONF_ENTER_ACTIONS: user_input.get(CONF_ENTER_ACTIONS) or [],
        CONF_EXIT_ACTIONS: user_input.get(CONF_EXIT_ACTIONS) or [],
    }


def _control_schema(
    defaults: dict[str, Any], states: list[dict[str, Any]]
) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_CONTROL_ENTITY,
            description={"suggested_value": defaults.get(CONF_CONTROL_ENTITY)},
        ): selector({"entity": {"filter": [{"domain": CONTROL_DOMAINS}]}}),
        vol.Required(
            CONF_CONTROL_TRIGGER,
            default=defaults.get(CONF_CONTROL_TRIGGER, TRIGGER_ANY),
        ): selector({"text": {}}),
        vol.Required(
            CONF_CONTROL_COMMAND,
            default=defaults.get(CONF_CONTROL_COMMAND, COMMAND_SET_STATE),
        ): selector(
            {
                "select": {
                    "options": list(CONTROL_COMMANDS),
                    "translation_key": "control_command",
                }
            }
        ),
    }
    if states:
        schema[
            vol.Optional(
                CONF_CONTROL_STATE,
                description={"suggested_value": defaults.get(CONF_CONTROL_STATE)},
            )
        ] = selector(
            {
                "select": {
                    "options": [
                        {
                            "value": state[CONF_STATE_ID],
                            "label": state[CONF_STATE_NAME],
                        }
                        for state in states
                    ]
                }
            }
        )
    schema[
        vol.Optional(CONF_DAYPARTS, default=list(defaults.get(CONF_DAYPARTS, [])))
    ] = _dayparts_selector()
    schema[
        vol.Optional(
            CONF_CONTROL_ACTIONS,
            description={"suggested_value": defaults.get(CONF_CONTROL_ACTIONS)},
        )
    ] = selector({"action": {}})
    return vol.Schema(schema)


def _command_fields_from_input(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_CONTROL_COMMAND: user_input.get(CONF_CONTROL_COMMAND, COMMAND_SET_STATE),
        CONF_CONTROL_STATE: user_input.get(CONF_CONTROL_STATE),
        CONF_CONTROL_ACTIONS: user_input.get(CONF_CONTROL_ACTIONS) or [],
        CONF_DAYPARTS: list(user_input.get(CONF_DAYPARTS, [])),
    }


def _dayparts_selector() -> Any:
    return selector(
        {
            "select": {
                "options": [daypart.value for daypart in Daypart],
                "multiple": True,
                "translation_key": "dayparts",
            }
        }
    )


def _control_from_input(user_input: dict[str, Any], control_id: str) -> dict[str, Any]:
    return {
        CONF_STATE_ID: control_id,
        CONF_CONTROL_KIND: CONTROL_KIND_ENTITY,
        CONF_CONTROL_ENTITY: user_input[CONF_CONTROL_ENTITY],
        CONF_CONTROL_TRIGGER: (
            user_input.get(CONF_CONTROL_TRIGGER) or TRIGGER_ANY
        ).strip(),
        **_command_fields_from_input(user_input),
    }


def _command_needs_state(user_input: dict[str, Any]) -> bool:
    return user_input.get(CONF_CONTROL_COMMAND, COMMAND_SET_STATE) in (
        COMMAND_SET_STATE,
        COMMAND_TOGGLE_STATE,
    ) and not user_input.get(CONF_CONTROL_STATE)


def _control_label(control: dict[str, Any]) -> str:
    command = control.get(CONF_CONTROL_COMMAND, COMMAND_SET_STATE)
    if control.get(CONF_CONTROL_KIND, CONTROL_KIND_ENTITY) == CONTROL_KIND_BUS:
        source = (
            f"{control.get(CONF_CONTROL_EVENT_TYPE)} "
            f"{control.get(CONF_CONTROL_EVENT_DATA, {})}"
        )
    else:
        source = (
            f"{control.get(CONF_CONTROL_ENTITY)} "
            f"({control.get(CONF_CONTROL_TRIGGER, TRIGGER_ANY)})"
        )
    return f"{source} → {command}"


def _suggest_control_id(control: dict[str, Any]) -> str:
    if control.get(CONF_CONTROL_KIND, CONTROL_KIND_ENTITY) == CONTROL_KIND_BUS:
        data = control.get(CONF_CONTROL_EVENT_DATA, {})
        hint = (
            data.get("command")
            or data.get("event")
            or data.get("subtype")
            or data.get("value")
            or "press"
        )
        return slugify(f"{control.get(CONF_CONTROL_EVENT_TYPE)}_{hint}") or "control"
    return (
        slugify(
            f"{control.get(CONF_CONTROL_ENTITY)}_"
            f"{control.get(CONF_CONTROL_TRIGGER, TRIGGER_ANY)}"
        )
        or "control"
    )


def _unique_control_id(controls: list[dict[str, Any]], base: str) -> str:
    existing = {control[CONF_STATE_ID] for control in controls}
    control_id = base
    suffix = 2
    while control_id in existing:
        control_id = f"{base}_{suffix}"
        suffix += 1
    return control_id


def _command_schema(
    defaults: dict[str, Any],
    states: list[dict[str, Any]],
    *,
    include_trigger: bool,
) -> vol.Schema:
    """The command half of a control form (used for discovered controls)."""
    schema: dict[Any, Any] = {}
    if include_trigger:
        schema[
            vol.Required(
                CONF_CONTROL_TRIGGER,
                default=defaults.get(CONF_CONTROL_TRIGGER, TRIGGER_ANY),
            )
        ] = selector({"text": {}})
    schema[
        vol.Required(
            CONF_CONTROL_COMMAND,
            default=defaults.get(CONF_CONTROL_COMMAND, COMMAND_SET_STATE),
        )
    ] = selector(
        {
            "select": {
                "options": list(CONTROL_COMMANDS),
                "translation_key": "control_command",
            }
        }
    )
    if states:
        schema[
            vol.Optional(
                CONF_CONTROL_STATE,
                description={"suggested_value": defaults.get(CONF_CONTROL_STATE)},
            )
        ] = selector(
            {
                "select": {
                    "options": [
                        {
                            "value": state[CONF_STATE_ID],
                            "label": state[CONF_STATE_NAME],
                        }
                        for state in states
                    ]
                }
            }
        )
    schema[
        vol.Optional(CONF_DAYPARTS, default=list(defaults.get(CONF_DAYPARTS, [])))
    ] = _dayparts_selector()
    schema[
        vol.Optional(
            CONF_CONTROL_ACTIONS,
            description={"suggested_value": defaults.get(CONF_CONTROL_ACTIONS)},
        )
    ] = selector({"action": {}})
    return vol.Schema(schema)


async def _async_capture_press(hass: HomeAssistant) -> dict[str, Any] | None:
    """Wait for the user to press the control they want to bind.

    Watches event entities (modern remotes) and the raw bus event types
    fired by remotes that never become entities (zha_event, hue_event, ...).
    The first press wins; returns None on timeout.
    """
    future: asyncio.Future[dict[str, Any]] = hass.loop.create_future()
    unsubs = []

    @callback
    def _capture(result: dict[str, Any]) -> None:
        if not future.done():
            future.set_result(result)

    @callback
    def _entity_listener(event: Event) -> None:
        entity_id = event.data.get("entity_id", "")
        if not entity_id.startswith("event."):
            return
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if (
            new_state is None
            or old_state is None
            or new_state.state in ("unknown", "unavailable")
            or new_state.state == old_state.state
        ):
            return
        _capture(
            {
                CONF_CONTROL_KIND: CONTROL_KIND_ENTITY,
                CONF_CONTROL_ENTITY: entity_id,
                CONF_CONTROL_TRIGGER: new_state.attributes.get("event_type")
                or TRIGGER_ANY,
            }
        )

    @callback
    def _bus_listener(event: Event) -> None:
        _capture(
            {
                CONF_CONTROL_KIND: CONTROL_KIND_BUS,
                CONF_CONTROL_EVENT_TYPE: event.event_type,
                CONF_CONTROL_EVENT_DATA: {
                    key: value
                    for key, value in event.data.items()
                    if isinstance(value, (str, int, float))
                },
            }
        )

    unsubs.append(hass.bus.async_listen("state_changed", _entity_listener))
    for event_type in CONTROLLER_EVENT_TYPES:
        unsubs.append(hass.bus.async_listen(event_type, _bus_listener))
    try:
        async with asyncio.timeout(CONTROL_CAPTURE_TIMEOUT):
            return await future
    except TimeoutError:
        return None
    finally:
        for unsub in unsubs:
            unsub()


def _describe_captured(captured: dict[str, Any]) -> str:
    if captured.get(CONF_CONTROL_KIND) == CONTROL_KIND_BUS:
        return (
            f"{captured.get(CONF_CONTROL_EVENT_TYPE)}: "
            f"{captured.get(CONF_CONTROL_EVENT_DATA)}"
        )
    return (
        f"{captured.get(CONF_CONTROL_ENTITY)} "
        f"({captured.get(CONF_CONTROL_TRIGGER)})"
    )


class LabsExperienceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a new space."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            self._async_abort_entries_match({CONF_NAME: name})
            options = _normalize_basics(
                {key: value for key, value in user_input.items() if key != CONF_NAME}
            )
            options.setdefault(CONF_PRESENCE_ENTITIES, [])
            area_id = options.get(CONF_AREA)
            if area_id:
                # Build the room profile from the area automatically;
                # explicit choices in the form always win.
                for key, value in _classify_area(self.hass, area_id).items():
                    if not options.get(key):
                        options[key] = value
            if not options.get(CONF_PRESENCE_ENTITIES):
                errors[CONF_PRESENCE_ENTITIES] = "presence_required"
            else:
                return self.async_create_entry(
                    title=name, data={CONF_NAME: name}, options=options
                )
        schema = vol.Schema(
            {vol.Required(CONF_NAME): selector({"text": {}})}
        ).extend(_basics_schema(user_input or {}).schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LabsExperienceOptionsFlow:
        return LabsExperienceOptionsFlow()


class LabsExperienceOptionsFlow(OptionsFlow):
    """Manage a space: basics, phase actions, and experience states."""

    def __init__(self) -> None:
        self._edit_state_id: str | None = None
        self._edit_control_id: str | None = None
        self._edit_ambiance_id: str | None = None
        self._capture_task: asyncio.Task[dict[str, Any] | None] | None = None
        self._captured: dict[str, Any] | None = None

    @property
    def _options(self) -> dict[str, Any]:
        return dict(self.config_entry.options)

    def _states(self) -> list[dict[str, Any]]:
        return [dict(state) for state in self.config_entry.options.get(CONF_STATES, [])]

    def _controls(self) -> list[dict[str, Any]]:
        return [
            dict(control)
            for control in self.config_entry.options.get(CONF_CONTROLS, [])
        ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "basics",
                "profile_menu",
                "states_menu",
                "controls_menu",
                "phase_actions",
            ],
        )

    def _ambiance_rules(self) -> list[dict[str, Any]]:
        return [
            dict(rule)
            for rule in self.config_entry.options.get(CONF_AMBIANCE_RULES, [])
        ]

    async def async_step_profile_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menu = ["profile"]
        if self._options.get(CONF_AREA):
            menu.append("fill_from_area")
        menu += ["lighting_settings", "climate_settings", "add_ambiance"]
        if self._ambiance_rules():
            menu += ["edit_ambiance", "remove_ambiance"]
        return self.async_show_menu(step_id="profile_menu", menu_options=menu)

    async def async_step_add_ambiance(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            rules = self._ambiance_rules()
            base = (
                slugify(
                    f"{user_input[CONF_AMBIANCE_ENTITY]}_"
                    f"{user_input.get(CONF_AMBIANCE_STATES, '')}"
                )
                or "ambiance"
            )
            rule_id = _unique_control_id(rules, base)
            rules.append(_ambiance_from_input(user_input, rule_id))
            options = self._options
            options[CONF_AMBIANCE_RULES] = rules
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="add_ambiance", data_schema=_ambiance_schema({})
        )

    async def async_step_edit_ambiance(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._edit_ambiance_id = user_input["rule"]
            return await self.async_step_edit_ambiance_form()
        schema = vol.Schema(
            {
                vol.Required("rule"): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "value": rule[CONF_STATE_ID],
                                    "label": _ambiance_label(rule),
                                }
                                for rule in self._ambiance_rules()
                            ]
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="edit_ambiance", data_schema=schema)

    async def async_step_edit_ambiance_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        rules = self._ambiance_rules()
        current = next(
            (
                rule
                for rule in rules
                if rule[CONF_STATE_ID] == self._edit_ambiance_id
            ),
            None,
        )
        if current is None:
            return self.async_abort(reason="rule_not_found")
        if user_input is not None:
            updated = _ambiance_from_input(user_input, current[CONF_STATE_ID])
            options = self._options
            options[CONF_AMBIANCE_RULES] = [
                updated if rule[CONF_STATE_ID] == current[CONF_STATE_ID] else rule
                for rule in rules
            ]
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="edit_ambiance_form", data_schema=_ambiance_schema(current)
        )

    async def async_step_remove_ambiance(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        rules = self._ambiance_rules()
        if user_input is not None:
            to_remove = set(user_input.get("rules", []))
            options = self._options
            options[CONF_AMBIANCE_RULES] = [
                rule for rule in rules if rule[CONF_STATE_ID] not in to_remove
            ]
            return self.async_create_entry(title="", data=options)
        schema = vol.Schema(
            {
                vol.Required("rules", default=[]): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "value": rule[CONF_STATE_ID],
                                    "label": _ambiance_label(rule),
                                }
                                for rule in rules
                            ],
                            "multiple": True,
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="remove_ambiance", data_schema=schema)

    async def async_step_states_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menu = ["add_starter_states", "add_state"]
        if self._states():
            menu += ["edit_state", "remove_states"]
        return self.async_show_menu(step_id="states_menu", menu_options=menu)

    async def async_step_controls_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menu = ["discover_control", "add_control"]
        if self._controls():
            menu += ["edit_control", "remove_controls"]
        return self.async_show_menu(step_id="controls_menu", menu_options=menu)

    async def async_step_add_starter_states(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        states = self._states()
        existing = {state[CONF_STATE_ID] for state in states}
        available = [
            template for template in STARTER_TEMPLATES if template not in existing
        ]
        if user_input is not None:
            selected = [
                template
                for template in user_input.get("templates", [])
                if template in available
            ]
            media_entity = user_input.get("media_entity")
            work_entity = user_input.get("work_entity")
            if not selected:
                errors["base"] = "no_templates"
            elif STARTER_MEDIA in selected and not media_entity:
                errors["base"] = "media_entity_required"
            elif STARTER_WORKING in selected and not work_entity:
                errors["base"] = "work_entity_required"
            else:
                options = self._options
                options[CONF_STATES] = states + _starter_states(
                    selected, media_entity, work_entity
                )
                return self.async_create_entry(title="", data=options)
        suggested_media = (self._options.get(CONF_MEDIA_ENTITIES) or [None])[0]
        schema = vol.Schema(
            {
                vol.Required("templates", default=list(available)): selector(
                    {
                        "select": {
                            "options": list(STARTER_TEMPLATES),
                            "multiple": True,
                            "translation_key": "starter_templates",
                        }
                    }
                ),
                vol.Optional(
                    "media_entity",
                    description={"suggested_value": suggested_media},
                ): selector({"entity": {"filter": [{"domain": ["media_player"]}]}}),
                vol.Optional("work_entity"): selector({"entity": {}}),
            }
        )
        return self.async_show_form(
            step_id="add_starter_states", data_schema=schema, errors=errors
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            for key in PROFILE_LIST_KEYS:
                options[key] = list(user_input.get(key, []))
            if user_input.get(CONF_ILLUMINANCE_SENSOR):
                options[CONF_ILLUMINANCE_SENSOR] = user_input[CONF_ILLUMINANCE_SENSOR]
            else:
                options.pop(CONF_ILLUMINANCE_SENSOR, None)
            options[CONF_LUX_THRESHOLD] = float(user_input[CONF_LUX_THRESHOLD])
            options[CONF_TARGET_LUX] = float(user_input[CONF_TARGET_LUX])
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="profile", data_schema=_profile_schema(self._options)
        )

    async def async_step_fill_from_area(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        options = self._options
        area_id = options.get(CONF_AREA)
        if not area_id:
            return self.async_abort(reason="no_area")
        # Fill only roles that are still empty; never clobber choices.
        for key, value in _classify_area(self.hass, area_id).items():
            if not options.get(key):
                options[key] = value
        return self.async_create_entry(title="", data=options)

    async def async_step_lighting_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            options.update(user_input)
            for key in (
                CONF_MIN_KELVIN,
                CONF_MAX_KELVIN,
                CONF_MIN_BRIGHTNESS,
                CONF_MAX_BRIGHTNESS,
                CONF_MANUAL_HOLD,
            ):
                options[key] = int(options[key])
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="lighting_settings", data_schema=_lighting_schema(self._options)
        )

    async def async_step_climate_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            options.update(user_input)
            options[CONF_WINDOW_PAUSE_DELAY] = int(options[CONF_WINDOW_PAUSE_DELAY])
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="climate_settings", data_schema=_climate_schema(self._options)
        )

    async def async_step_basics(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            options.pop(CONF_AREA, None)
            options.update(_normalize_basics(user_input))
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="basics", data_schema=_basics_schema(self._options)
        )

    async def async_step_phase_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        action_keys = (
            CONF_WAKE_ACTIONS,
            CONF_COOLDOWN_ACTIONS,
            CONF_VACANT_ACTIONS,
            CONF_PASS_THROUGH_ACTIONS,
        )
        if user_input is not None:
            options = self._options
            for key in action_keys:
                options[key] = user_input.get(key) or []
            return self.async_create_entry(title="", data=options)
        options = self._options
        schema = vol.Schema(
            {
                vol.Optional(
                    key, description={"suggested_value": options.get(key)}
                ): selector({"action": {}})
                for key in action_keys
            }
        )
        return self.async_show_form(step_id="phase_actions", data_schema=schema)

    async def async_step_add_state(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input = flatten_state_input(user_input)
            states = self._states()
            existing_ids = {state[CONF_STATE_ID] for state in states}
            base = slugify(user_input[CONF_STATE_NAME]) or "state"
            state_id = base
            suffix = 2
            while state_id in existing_ids:
                state_id = f"{base}_{suffix}"
                suffix += 1
            states.append(_state_from_input(user_input, state_id))
            options = self._options
            options[CONF_STATES] = states
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="add_state", data_schema=_state_schema({}))

    async def async_step_edit_state(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._edit_state_id = user_input["state"]
            return await self.async_step_edit_state_form()
        schema = vol.Schema(
            {
                vol.Required("state"): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "value": state[CONF_STATE_ID],
                                    "label": state[CONF_STATE_NAME],
                                }
                                for state in self._states()
                            ]
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="edit_state", data_schema=schema)

    async def async_step_edit_state_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        states = self._states()
        current = next(
            (state for state in states if state[CONF_STATE_ID] == self._edit_state_id),
            None,
        )
        if current is None:
            return self.async_abort(reason="state_not_found")
        if user_input is not None:
            user_input = flatten_state_input(user_input)
            updated = _state_from_input(user_input, current[CONF_STATE_ID])
            options = self._options
            options[CONF_STATES] = [
                updated if state[CONF_STATE_ID] == current[CONF_STATE_ID] else state
                for state in states
            ]
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="edit_state_form", data_schema=_state_schema(current)
        )

    async def async_step_add_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if _command_needs_state(user_input):
                errors["base"] = "state_required"
            else:
                controls = self._controls()
                new_control = _control_from_input(user_input, "")
                new_control[CONF_STATE_ID] = _unique_control_id(
                    controls, _suggest_control_id(new_control)
                )
                controls.append(new_control)
                options = self._options
                options[CONF_CONTROLS] = controls
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="add_control",
            data_schema=_control_schema(user_input or {}, self._states()),
            errors=errors,
        )

    async def async_step_discover_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._capture_task is None:
            self._capture_task = self.hass.async_create_task(
                _async_capture_press(self.hass)
            )
        if not self._capture_task.done():
            return self.async_show_progress(
                progress_action="press_control",
                progress_task=self._capture_task,
            )
        self._captured = self._capture_task.result()
        self._capture_task = None
        if self._captured is None:
            return self.async_show_progress_done(next_step_id="discover_timeout")
        return self.async_show_progress_done(next_step_id="discover_control_form")

    async def async_step_discover_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="no_press_detected")

    async def async_step_discover_control_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        captured = self._captured or {}
        is_entity = (
            captured.get(CONF_CONTROL_KIND, CONTROL_KIND_ENTITY)
            == CONTROL_KIND_ENTITY
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            if _command_needs_state(user_input):
                errors["base"] = "state_required"
            else:
                controls = self._controls()
                new_control = {**captured, **_command_fields_from_input(user_input)}
                if is_entity:
                    new_control[CONF_CONTROL_TRIGGER] = (
                        user_input.get(CONF_CONTROL_TRIGGER) or TRIGGER_ANY
                    ).strip()
                new_control[CONF_STATE_ID] = _unique_control_id(
                    controls, _suggest_control_id(new_control)
                )
                controls.append(new_control)
                options = self._options
                options[CONF_CONTROLS] = controls
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="discover_control_form",
            data_schema=_command_schema(
                user_input or captured, self._states(), include_trigger=is_entity
            ),
            errors=errors,
            description_placeholders={"captured": _describe_captured(captured)},
        )

    async def async_step_edit_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._edit_control_id = user_input["control"]
            return await self.async_step_edit_control_form()
        schema = vol.Schema(
            {
                vol.Required("control"): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "value": control[CONF_STATE_ID],
                                    "label": _control_label(control),
                                }
                                for control in self._controls()
                            ]
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="edit_control", data_schema=schema)

    async def async_step_edit_control_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        controls = self._controls()
        current = next(
            (
                control
                for control in controls
                if control[CONF_STATE_ID] == self._edit_control_id
            ),
            None,
        )
        if current is None:
            return self.async_abort(reason="control_not_found")
        is_bus = current.get(CONF_CONTROL_KIND, CONTROL_KIND_ENTITY) == CONTROL_KIND_BUS
        errors: dict[str, str] = {}
        if user_input is not None:
            if _command_needs_state(user_input):
                errors["base"] = "state_required"
            else:
                if is_bus:
                    # Bus bindings keep their captured event identity.
                    updated = {**current, **_command_fields_from_input(user_input)}
                else:
                    updated = _control_from_input(user_input, current[CONF_STATE_ID])
                options = self._options
                options[CONF_CONTROLS] = [
                    updated
                    if control[CONF_STATE_ID] == current[CONF_STATE_ID]
                    else control
                    for control in controls
                ]
                return self.async_create_entry(title="", data=options)
        if is_bus:
            schema = _command_schema(
                user_input or current, self._states(), include_trigger=False
            )
        else:
            schema = _control_schema(user_input or current, self._states())
        return self.async_show_form(
            step_id="edit_control_form",
            data_schema=schema,
            errors=errors,
            description_placeholders={"captured": _describe_captured(current)},
        )

    async def async_step_remove_controls(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        controls = self._controls()
        if user_input is not None:
            to_remove = set(user_input.get("controls", []))
            options = self._options
            options[CONF_CONTROLS] = [
                control
                for control in controls
                if control[CONF_STATE_ID] not in to_remove
            ]
            return self.async_create_entry(title="", data=options)
        schema = vol.Schema(
            {
                vol.Required("controls", default=[]): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "value": control[CONF_STATE_ID],
                                    "label": _control_label(control),
                                }
                                for control in controls
                            ],
                            "multiple": True,
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="remove_controls", data_schema=schema)

    async def async_step_remove_states(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        states = self._states()
        if user_input is not None:
            to_remove = set(user_input.get("states", []))
            options = self._options
            options[CONF_STATES] = [
                state for state in states if state[CONF_STATE_ID] not in to_remove
            ]
            return self.async_create_entry(title="", data=options)
        schema = vol.Schema(
            {
                vol.Required("states", default=[]): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "value": state[CONF_STATE_ID],
                                    "label": state[CONF_STATE_NAME],
                                }
                                for state in states
                            ],
                            "multiple": True,
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="remove_states", data_schema=schema)
