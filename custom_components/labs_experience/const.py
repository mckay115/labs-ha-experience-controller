"""Constants for the Labs Experience Controller integration."""

from __future__ import annotations

from enum import StrEnum

DOMAIN = "labs_experience"

EVENT_TYPE = "labs_experience_event"
EVENT_PHASE_CHANGED = "phase_changed"
EVENT_STATE_CHANGED = "state_changed"
EVENT_PASSING_THROUGH = "passing_through"

CONF_AREA = "area_id"
CONF_PRESENCE_ENTITIES = "presence_entities"
CONF_PRESENCE_MATCH = "presence_match"
CONF_WAKE_DURATION = "wake_duration"
CONF_CLEAR_DELAY = "clear_delay"
CONF_PASS_THROUGH_DELAY = "pass_through_delay"
CONF_COOLDOWN_DURATION = "cooldown_duration"
CONF_WAKE_ACTIONS = "wake_actions"
CONF_COOLDOWN_ACTIONS = "cooldown_actions"
CONF_VACANT_ACTIONS = "vacant_actions"
CONF_PASS_THROUGH_ACTIONS = "pass_through_actions"
CONF_STATES = "states"
CONF_CONTROLS = "controls"

CONF_STATE_ID = "id"
CONF_STATE_NAME = "name"
CONF_STATE_ICON = "icon"
CONF_PRIORITY = "priority"
CONF_EVIDENCE_ENTITIES = "evidence_entities"
CONF_EVIDENCE_MODE = "evidence_mode"
CONF_ACTIVE_STATES = "active_states"
CONF_ENTER_ACTIONS = "enter_actions"
CONF_EXIT_ACTIONS = "exit_actions"
CONF_HOLD_OCCUPANCY = "hold_occupancy"
CONF_DAYPARTS = "dayparts"

# Room profile roles
CONF_LIGHTS_AMBIENT = "lights_ambient"
CONF_LIGHTS_TASK = "lights_task"
CONF_LIGHTS_ACCENT = "lights_accent"
CONF_LIGHTS_NIGHT = "lights_night"
LIGHT_ROLE_AMBIENT = "ambient"
LIGHT_ROLE_TASK = "task"
LIGHT_ROLE_ACCENT = "accent"
LIGHT_ROLE_NIGHT = "night"
LIGHT_ROLES = [
    LIGHT_ROLE_AMBIENT,
    LIGHT_ROLE_TASK,
    LIGHT_ROLE_ACCENT,
    LIGHT_ROLE_NIGHT,
]
LIGHT_ROLE_KEYS = {
    LIGHT_ROLE_AMBIENT: CONF_LIGHTS_AMBIENT,
    LIGHT_ROLE_TASK: CONF_LIGHTS_TASK,
    LIGHT_ROLE_ACCENT: CONF_LIGHTS_ACCENT,
    LIGHT_ROLE_NIGHT: CONF_LIGHTS_NIGHT,
}
CONF_CLIMATE_ENTITIES = "climate_entities"
CONF_WINDOW_SENSORS = "window_sensors"
CONF_DOOR_SENSORS = "door_sensors"
CONF_MEDIA_ENTITIES = "media_entities"
CONF_APPLIANCE_ENTITIES = "appliance_entities"
CONF_ILLUMINANCE_SENSOR = "illuminance_sensor"
CONF_LUX_THRESHOLD = "lux_threshold"
CONF_TARGET_LUX = "target_lux"
DEFAULT_LUX_THRESHOLD = 50
DEFAULT_TARGET_LUX = 0  # 0 = lux-compensated brightness disabled

# Closed-loop lux compensation tuning
LUX_DEADBAND = 0.15  # fraction of target inside which we leave lights alone
LUX_MAX_STEP = 20  # largest single brightness adjustment, percent
LUX_ADJUST_INTERVAL = 60  # seconds between adjustments (anti-oscillation)

# Lighting facet
CONF_AUTO_LIGHTING = "auto_lighting"
CONF_CIRCADIAN = "circadian_enabled"
CONF_MIN_KELVIN = "min_kelvin"
CONF_MAX_KELVIN = "max_kelvin"
CONF_MIN_BRIGHTNESS = "min_brightness"
CONF_MAX_BRIGHTNESS = "max_brightness"
CONF_MANUAL_HOLD = "manual_hold"
DEFAULT_MIN_KELVIN = 2200
DEFAULT_MAX_KELVIN = 5500
DEFAULT_MIN_BRIGHTNESS = 35
DEFAULT_MAX_BRIGHTNESS = 100
DEFAULT_MANUAL_HOLD = 0  # minutes; 0 = manual holds until the space is vacant

# Per-state lighting spec
CONF_LIGHT_ROLES = "light_roles"
CONF_LIGHT_BRIGHTNESS = "light_brightness"
CONF_LIGHT_COLOR = "light_color"
CONF_LIGHT_EXCLUSIVE = "light_exclusive"
LIGHT_COLOR_CIRCADIAN = "circadian"
LIGHT_COLOR_MODES = [LIGHT_COLOR_CIRCADIAN, "warm", "neutral", "cool"]
COLOR_KELVIN = {"warm": 2700, "neutral": 4000, "cool": 5500}

# Climate facet
CONF_CLIMATE_INTENT = "climate_intent"
CLIMATE_INTENT_KEEP = "keep"
CLIMATE_INTENT_COMFORT = "comfort"
CLIMATE_INTENT_ECO = "eco"
CLIMATE_INTENT_OFF = "off"
CLIMATE_INTENTS = [
    CLIMATE_INTENT_KEEP,
    CLIMATE_INTENT_COMFORT,
    CLIMATE_INTENT_ECO,
    CLIMATE_INTENT_OFF,
]
CONF_COMFORT_TEMP = "comfort_temp"
CONF_ECO_TEMP = "eco_temp"
CONF_VACANT_CLIMATE = "vacant_climate"
CONF_WINDOW_PAUSE_DELAY = "window_pause_delay"
DEFAULT_COMFORT_TEMP = 21.0
DEFAULT_ECO_TEMP = 17.0
DEFAULT_VACANT_CLIMATE = CLIMATE_INTENT_KEEP
DEFAULT_WINDOW_PAUSE_DELAY = 120

# Daypart boundaries ("HH:MM" local time; night wraps midnight)
CONF_MORNING_START = "morning_start"
CONF_DAY_START = "day_start"
CONF_EVENING_START = "evening_start"
CONF_NIGHT_START = "night_start"
DEFAULT_MORNING_START = "06:00"
DEFAULT_DAY_START = "10:00"
DEFAULT_EVENING_START = "18:00"
DEFAULT_NIGHT_START = "22:00"

CONF_CONTROL_ENTITY = "entity_id"
CONF_CONTROL_TRIGGER = "trigger"
CONF_CONTROL_COMMAND = "command"
CONF_CONTROL_STATE = "state_id"
CONF_CONTROL_ACTIONS = "actions"
CONF_CONTROL_KIND = "kind"
CONF_CONTROL_EVENT_TYPE = "event_type"
CONF_CONTROL_EVENT_DATA = "event_data"

CONTROL_KIND_ENTITY = "entity"
CONTROL_KIND_BUS = "bus_event"

# Bus event types fired by button remotes that never become entities.
# Used both for engine dispatch and press-to-program discovery.
CONTROLLER_EVENT_TYPES = [
    "zha_event",
    "deconz_event",
    "hue_event",
    "lutron_caseta_button_event",
    "zwave_js_value_notification",
    "zwave_js_notification",
    "knx_event",
    "shelly.click",
    "tasmota_event",
]

CONTROL_CAPTURE_TIMEOUT = 30

EVIDENCE_MODE_ANY = "any"
EVIDENCE_MODE_ALL = "all"

TRIGGER_ANY = "any"

COMMAND_SET_STATE = "set_state"
COMMAND_CYCLE_STATES = "cycle_states"
COMMAND_RESUME_AUTOMATIC = "resume_automatic"
COMMAND_WAKE = "wake"
COMMAND_MAKE_VACANT = "make_vacant"
COMMAND_TOGGLE_AUTOMATION = "toggle_automation"
COMMAND_RUN_ACTIONS = "run_actions"
COMMAND_LIGHTS_ON = "lights_on"
COMMAND_LIGHTS_OFF = "lights_off"
COMMAND_BRIGHTEN = "brighten"
COMMAND_DIM = "dim"

CONTROL_COMMANDS = [
    COMMAND_SET_STATE,
    COMMAND_CYCLE_STATES,
    COMMAND_RESUME_AUTOMATIC,
    COMMAND_WAKE,
    COMMAND_MAKE_VACANT,
    COMMAND_TOGGLE_AUTOMATION,
    COMMAND_RUN_ACTIONS,
    COMMAND_LIGHTS_ON,
    COMMAND_LIGHTS_OFF,
    COMMAND_BRIGHTEN,
    COMMAND_DIM,
]

DEFAULT_WAKE_DURATION = 20
DEFAULT_CLEAR_DELAY = 300
DEFAULT_PASS_THROUGH_DELAY = 60
DEFAULT_COOLDOWN_DURATION = 60
DEFAULT_ACTIVE_STATES = "on,playing,buffering,home,occupied,open,detected"

FALLBACK_STATE_ID = "occupied"

# Covers classic motion/occupancy, presence trackers, and mmWave sensors
# (Aqara FP1/FP2-class devices report present/moving/stationary). Numeric
# states are handled separately: any count > 0 is presence.
PRESENCE_ACTIVE_STATES = {
    "on",
    "home",
    "occupied",
    "detected",
    "present",
    "moving",
    "stationary",
}

SERVICE_SET_STATE = "set_state"
SERVICE_CLEAR_OVERRIDE = "clear_override"

ATTR_STATE = "state"


class Phase(StrEnum):
    """Occupancy lifecycle phases of a space."""

    VACANT = "vacant"
    WAKING = "waking"
    OCCUPIED = "occupied"
    COOLDOWN = "cooldown"


class Daypart(StrEnum):
    """The time-of-body layer used by circadian defaults and state gating."""

    MORNING = "morning"
    DAY = "day"
    EVENING = "evening"
    NIGHT = "night"


class Authority(StrEnum):
    """Who currently controls a facet of the space."""

    AUTO = "auto"
    MANUAL = "manual"
