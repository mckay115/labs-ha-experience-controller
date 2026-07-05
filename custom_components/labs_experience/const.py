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

CONF_CONTROL_ENTITY = "entity_id"
CONF_CONTROL_TRIGGER = "trigger"
CONF_CONTROL_COMMAND = "command"
CONF_CONTROL_STATE = "state_id"
CONF_CONTROL_ACTIONS = "actions"

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

CONTROL_COMMANDS = [
    COMMAND_SET_STATE,
    COMMAND_CYCLE_STATES,
    COMMAND_RESUME_AUTOMATIC,
    COMMAND_WAKE,
    COMMAND_MAKE_VACANT,
    COMMAND_TOGGLE_AUTOMATION,
    COMMAND_RUN_ACTIONS,
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
