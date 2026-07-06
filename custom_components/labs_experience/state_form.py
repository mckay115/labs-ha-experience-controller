"""The experience-state form: three fields up top, the rest in sections.

Sections keep the form approachable (the review found ~15 flat fields
intimidating) while preserving every capability. The frontend returns
section data nested; `flatten_state_input` restores the flat storage
shape the rest of the integration uses.
"""

from __future__ import annotations

from typing import Any

from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import selector
import voluptuous as vol

from .const import (
    CLIMATE_INTENT_KEEP,
    CLIMATE_INTENTS,
    CONF_ACTIVE_STATES,
    CONF_CLIMATE_INTENT,
    CONF_DAYPARTS,
    CONF_ENTER_ACTIONS,
    CONF_EVIDENCE_ENTITIES,
    CONF_EVIDENCE_MODE,
    CONF_EXIT_ACTIONS,
    CONF_HOLD_OCCUPANCY,
    CONF_LIGHT_BRIGHTNESS,
    CONF_LIGHT_COLOR,
    CONF_LIGHT_EXCLUSIVE,
    CONF_LIGHT_ROLES,
    CONF_PRIORITY,
    CONF_STATE_ICON,
    CONF_STATE_NAME,
    DEFAULT_ACTIVE_STATES,
    EVIDENCE_MODE_ALL,
    EVIDENCE_MODE_ANY,
    LIGHT_COLOR_CIRCADIAN,
    LIGHT_COLOR_MODES,
    LIGHT_ROLES,
    Daypart,
)

SECTION_EVIDENCE = "evidence"
SECTION_COMFORT = "comfort"
SECTION_ACTIONS = "actions"
STATE_FORM_SECTIONS = (SECTION_EVIDENCE, SECTION_COMFORT, SECTION_ACTIONS)


def flatten_state_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Merge the nested section payloads back into a flat state dict."""
    flat = dict(user_input)
    for key in STATE_FORM_SECTIONS:
        flat.update(flat.pop(key, None) or {})
    return flat


def state_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_STATE_NAME, default=defaults.get(CONF_STATE_NAME, "")
            ): selector({"text": {}}),
            vol.Optional(
                CONF_STATE_ICON,
                description={"suggested_value": defaults.get(CONF_STATE_ICON)},
            ): selector({"icon": {}}),
            vol.Required(
                CONF_PRIORITY, default=int(defaults.get(CONF_PRIORITY, 0))
            ): selector(
                {"number": {"min": -1000, "max": 1000, "step": 1, "mode": "box"}}
            ),
            vol.Required(SECTION_EVIDENCE): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EVIDENCE_ENTITIES,
                            default=list(defaults.get(CONF_EVIDENCE_ENTITIES, [])),
                        ): selector({"entity": {"multiple": True}}),
                        vol.Required(
                            CONF_EVIDENCE_MODE,
                            default=defaults.get(
                                CONF_EVIDENCE_MODE, EVIDENCE_MODE_ANY
                            ),
                        ): selector(
                            {
                                "select": {
                                    "options": [
                                        EVIDENCE_MODE_ANY,
                                        EVIDENCE_MODE_ALL,
                                    ],
                                    "translation_key": "evidence_mode",
                                }
                            }
                        ),
                        vol.Required(
                            CONF_ACTIVE_STATES,
                            default=defaults.get(
                                CONF_ACTIVE_STATES, DEFAULT_ACTIVE_STATES
                            ),
                        ): selector({"text": {}}),
                        vol.Required(
                            CONF_HOLD_OCCUPANCY,
                            default=bool(defaults.get(CONF_HOLD_OCCUPANCY, False)),
                        ): selector({"boolean": {}}),
                        vol.Optional(
                            CONF_DAYPARTS,
                            default=list(defaults.get(CONF_DAYPARTS, [])),
                        ): selector(
                            {
                                "select": {
                                    "options": [
                                        daypart.value for daypart in Daypart
                                    ],
                                    "multiple": True,
                                    "translation_key": "dayparts",
                                }
                            }
                        ),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required(SECTION_COMFORT): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_LIGHT_ROLES,
                            default=list(defaults.get(CONF_LIGHT_ROLES, [])),
                        ): selector(
                            {
                                "select": {
                                    "options": list(LIGHT_ROLES),
                                    "multiple": True,
                                    "translation_key": "light_roles",
                                }
                            }
                        ),
                        vol.Optional(
                            CONF_LIGHT_BRIGHTNESS,
                            description={
                                "suggested_value": defaults.get(CONF_LIGHT_BRIGHTNESS)
                            },
                        ): selector(
                            {
                                "number": {
                                    "min": 1,
                                    "max": 100,
                                    "unit_of_measurement": "%",
                                    "mode": "box",
                                }
                            }
                        ),
                        vol.Required(
                            CONF_LIGHT_COLOR,
                            default=defaults.get(
                                CONF_LIGHT_COLOR, LIGHT_COLOR_CIRCADIAN
                            ),
                        ): selector(
                            {
                                "select": {
                                    "options": list(LIGHT_COLOR_MODES),
                                    "translation_key": "light_color",
                                }
                            }
                        ),
                        vol.Required(
                            CONF_LIGHT_EXCLUSIVE,
                            default=bool(defaults.get(CONF_LIGHT_EXCLUSIVE, True)),
                        ): selector({"boolean": {}}),
                        vol.Required(
                            CONF_CLIMATE_INTENT,
                            default=defaults.get(
                                CONF_CLIMATE_INTENT, CLIMATE_INTENT_KEEP
                            ),
                        ): selector(
                            {
                                "select": {
                                    "options": list(CLIMATE_INTENTS),
                                    "translation_key": "climate_intent",
                                }
                            }
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required(SECTION_ACTIONS): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_ENTER_ACTIONS,
                            description={
                                "suggested_value": defaults.get(CONF_ENTER_ACTIONS)
                            },
                        ): selector({"action": {}}),
                        vol.Optional(
                            CONF_EXIT_ACTIONS,
                            description={
                                "suggested_value": defaults.get(CONF_EXIT_ACTIONS)
                            },
                        ): selector({"action": {}}),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )
