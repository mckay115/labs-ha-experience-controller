"""Bus-event control bindings and press-to-program capture."""

import asyncio

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.labs_experience.config_flow import _async_capture_press
from custom_components.labs_experience.const import (
    CONF_CONTROL_ENTITY,
    CONF_CONTROL_EVENT_DATA,
    CONF_CONTROL_EVENT_TYPE,
    CONF_CONTROL_KIND,
    CONF_CONTROL_TRIGGER,
    CONTROL_KIND_BUS,
    CONTROL_KIND_ENTITY,
    DOMAIN,
)

SELECT = "select.hall_experience"
PHASE = "sensor.hall_phase"


def make_hall() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hall",
        data={"name": "Hall"},
        options={
            "presence_entities": ["binary_sensor.hall_motion"],
            "wake_duration": 5,
            "clear_delay": 30,
            "pass_through_delay": 5,
            "cooldown_duration": 5,
            "states": [
                {"id": "bright", "name": "Bright", "priority": 0},
            ],
            "controls": [
                {
                    "id": "zha_toggle",
                    "kind": CONTROL_KIND_BUS,
                    "event_type": "zha_event",
                    "event_data": {"device_ieee": "aa:bb:cc", "command": "toggle"},
                    "command": "set_state",
                    "state_id": "bright",
                }
            ],
        },
    )


async def test_bus_event_control(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.hall_motion", "off")
    entry = make_hall()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "vacant"

    # Same device, different button command: no binding, nothing happens.
    hass.bus.async_fire(
        "zha_event", {"device_ieee": "aa:bb:cc", "command": "off", "args": []}
    )
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "vacant"

    # The bound press wakes the hall into the pinned state. Extra event
    # keys (args, endpoint) don't matter — the binding matches a subset.
    hass.bus.async_fire(
        "zha_event",
        {
            "device_ieee": "aa:bb:cc",
            "command": "toggle",
            "endpoint_id": 1,
            "args": [],
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "occupied"
    assert hass.states.get(SELECT).state == "Bright"


async def test_daypart_restricted_control(hass: HomeAssistant, freezer) -> None:
    """The same button does different things at different times of day."""
    freezer.move_to("2026-07-05 23:00:00+00:00")  # night, UTC
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Hall",
        data={"name": "Hall"},
        options={
            "presence_entities": ["binary_sensor.hall_motion"],
            "wake_duration": 5,
            "clear_delay": 30,
            "pass_through_delay": 5,
            "cooldown_duration": 5,
            "states": [
                {"id": "bright", "name": "Bright", "priority": 0},
                {"id": "dim_night", "name": "Dim night", "priority": 5},
            ],
            "controls": [
                {
                    "id": "day_press",
                    "entity_id": "event.button",
                    "trigger": "single",
                    "command": "set_state",
                    "state_id": "bright",
                    "dayparts": ["morning", "day"],
                },
                {
                    "id": "night_press",
                    "entity_id": "event.button",
                    "trigger": "single",
                    "command": "set_state",
                    "state_id": "dim_night",
                    "dayparts": ["evening", "night"],
                },
            ],
        },
    )
    await hass.config.async_set_time_zone("UTC")
    hass.states.async_set("binary_sensor.hall_motion", "off")
    hass.states.async_set(
        "event.button", "2026-07-05T22:00:00+00:00", {"event_type": "initial"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # At night, the night binding wins; the day binding stays silent.
    hass.states.async_set(
        "event.button", "2026-07-05T23:00:05+00:00", {"event_type": "single"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "occupied"
    assert hass.states.get(SELECT).state == "Dim night"


async def test_capture_press_bus_event(hass: HomeAssistant) -> None:
    task = hass.async_create_task(_async_capture_press(hass))
    await asyncio.sleep(0)

    hass.bus.async_fire(
        "zha_event",
        {"device_ieee": "aa:bb:cc", "command": "on", "args": [1, 2], "params": {}},
    )
    captured = await task

    assert captured[CONF_CONTROL_KIND] == CONTROL_KIND_BUS
    assert captured[CONF_CONTROL_EVENT_TYPE] == "zha_event"
    # Only scalar keys are kept for matching.
    assert captured[CONF_CONTROL_EVENT_DATA] == {
        "device_ieee": "aa:bb:cc",
        "command": "on",
    }


async def test_capture_press_event_entity(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "event.remote", "2026-01-01T00:00:00+00:00", {"event_type": "initial"}
    )
    await hass.async_block_till_done()

    task = hass.async_create_task(_async_capture_press(hass))
    await asyncio.sleep(0)

    hass.states.async_set(
        "event.remote", "2026-01-01T00:00:01+00:00", {"event_type": "double"}
    )
    captured = await task

    assert captured[CONF_CONTROL_KIND] == CONTROL_KIND_ENTITY
    assert captured[CONF_CONTROL_ENTITY] == "event.remote"
    assert captured[CONF_CONTROL_TRIGGER] == "double"
