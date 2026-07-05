"""Config and options flows for Labs Experience Controller."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.selector import selector
from homeassistant.util import slugify

from .const import (
    COMMAND_SET_STATE,
    CONF_ACTIVE_STATES,
    CONF_AREA,
    CONF_CLEAR_DELAY,
    CONF_CONTROL_ACTIONS,
    CONF_CONTROL_COMMAND,
    CONF_CONTROL_ENTITY,
    CONF_CONTROL_EVENT_DATA,
    CONF_CONTROL_EVENT_TYPE,
    CONF_CONTROL_KIND,
    CONF_CONTROL_STATE,
    CONF_CONTROL_TRIGGER,
    CONF_CONTROLS,
    CONTROL_CAPTURE_TIMEOUT,
    CONTROL_KIND_BUS,
    CONTROL_KIND_ENTITY,
    CONTROLLER_EVENT_TYPES,
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
    CONTROL_COMMANDS,
    DEFAULT_ACTIVE_STATES,
    DEFAULT_CLEAR_DELAY,
    DEFAULT_COOLDOWN_DURATION,
    DEFAULT_PASS_THROUGH_DELAY,
    DEFAULT_WAKE_DURATION,
    DOMAIN,
    EVIDENCE_MODE_ALL,
    EVIDENCE_MODE_ANY,
    TRIGGER_ANY,
)

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


def _state_schema(defaults: dict[str, Any]) -> vol.Schema:
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
            ): selector({"number": {"min": -1000, "max": 1000, "step": 1, "mode": "box"}}),
            vol.Optional(
                CONF_EVIDENCE_ENTITIES,
                default=list(defaults.get(CONF_EVIDENCE_ENTITIES, [])),
            ): selector({"entity": {"multiple": True}}),
            vol.Required(
                CONF_EVIDENCE_MODE,
                default=defaults.get(CONF_EVIDENCE_MODE, EVIDENCE_MODE_ANY),
            ): selector(
                {
                    "select": {
                        "options": [EVIDENCE_MODE_ANY, EVIDENCE_MODE_ALL],
                        "translation_key": "evidence_mode",
                    }
                }
            ),
            vol.Required(
                CONF_ACTIVE_STATES,
                default=defaults.get(CONF_ACTIVE_STATES, DEFAULT_ACTIVE_STATES),
            ): selector({"text": {}}),
            vol.Required(
                CONF_HOLD_OCCUPANCY,
                default=bool(defaults.get(CONF_HOLD_OCCUPANCY, False)),
            ): selector({"boolean": {}}),
            vol.Optional(
                CONF_ENTER_ACTIONS,
                description={"suggested_value": defaults.get(CONF_ENTER_ACTIONS)},
            ): selector({"action": {}}),
            vol.Optional(
                CONF_EXIT_ACTIONS,
                description={"suggested_value": defaults.get(CONF_EXIT_ACTIONS)},
            ): selector({"action": {}}),
        }
    )


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
    }


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
    return user_input.get(
        CONF_CONTROL_COMMAND, COMMAND_SET_STATE
    ) == COMMAND_SET_STATE and not user_input.get(CONF_CONTROL_STATE)


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
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            self._async_abort_entries_match({CONF_NAME: name})
            options = _normalize_basics(
                {key: value for key, value in user_input.items() if key != CONF_NAME}
            )
            return self.async_create_entry(
                title=name, data={CONF_NAME: name}, options=options
            )
        schema = vol.Schema(
            {vol.Required(CONF_NAME): selector({"text": {}})}
        ).extend(_basics_schema({}).schema)
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LabsExperienceOptionsFlow:
        return LabsExperienceOptionsFlow()


class LabsExperienceOptionsFlow(OptionsFlow):
    """Manage a space: basics, phase actions, and experience states."""

    def __init__(self) -> None:
        self._edit_state_id: str | None = None
        self._edit_control_id: str | None = None
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
        menu = ["basics", "phase_actions", "add_state"]
        if self._states():
            menu += ["edit_state", "remove_states"]
        menu += ["discover_control", "add_control"]
        if self._controls():
            menu += ["edit_control", "remove_controls"]
        return self.async_show_menu(step_id="init", menu_options=menu)

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
