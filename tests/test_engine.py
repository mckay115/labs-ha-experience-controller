"""End-to-end tests for the space engine through real HA entities."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from homeassistant.core import HomeAssistant

from custom_components.labs_experience.const import DOMAIN, EVENT_TYPE

WAKE = 10
CLEAR = 30
PASS = 5
COOL = 15

SELECT = "select.living_room_experience"
PHASE = "sensor.living_room_phase"
OCCUPIED = "binary_sensor.living_room_occupied"
AUTOMATION = "switch.living_room_automation"
RESUME = "button.living_room_resume_automatic"


def make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        data={"name": "Living Room"},
        options={
            "presence_entities": ["binary_sensor.motion"],
            "wake_duration": WAKE,
            "clear_delay": CLEAR,
            "pass_through_delay": PASS,
            "cooldown_duration": COOL,
            "states": [
                {
                    "id": "hanging_out",
                    "name": "Hanging out",
                    "priority": 0,
                    "evidence_entities": [],
                    "enter_actions": [{"event": "test_hangout_enter"}],
                },
                {
                    "id": "watching_tv",
                    "name": "Watching TV",
                    "priority": 10,
                    "evidence_entities": ["media_player.tv"],
                    "active_states": "playing,buffering",
                    "hold_occupancy": True,
                },
            ],
            "controls": [
                {
                    "id": "remote_single",
                    "entity_id": "event.remote",
                    "trigger": "single",
                    "command": "set_state",
                    "state_id": "watching_tv",
                }
            ],
        },
    )


async def setup_space(hass: HomeAssistant) -> MockConfigEntry:
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("media_player.tv", "idle")
    hass.states.async_set(
        "event.remote", "2026-01-01T00:00:00.000+00:00", {"event_type": "initial"}
    )
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def advance(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def occupy(hass: HomeAssistant, freezer) -> None:
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)


async def test_wake_then_occupied_baseline(hass: HomeAssistant, freezer) -> None:
    enter_events = async_capture_events(hass, "test_hangout_enter")
    await setup_space(hass)

    assert hass.states.get(PHASE).state == "vacant"
    assert hass.states.get(SELECT).state == "unavailable"
    assert hass.states.get(OCCUPIED).state == "off"

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "waking"
    assert hass.states.get(OCCUPIED).state == "on"

    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(PHASE).state == "occupied"
    assert hass.states.get(SELECT).state == "Hanging out"
    assert len(enter_events) == 1


async def test_evidence_inference_and_hold(hass: HomeAssistant, freezer) -> None:
    await setup_space(hass)
    await occupy(hass, freezer)

    hass.states.async_set("media_player.tv", "playing")
    await hass.async_block_till_done()
    assert hass.states.get(SELECT).state == "Watching TV"

    # Motion stops mid-movie; the hold keeps the space occupied.
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, CLEAR + 5)
    assert hass.states.get(PHASE).state == "occupied"

    # Movie ends with nobody moving: hold releases, clear countdown runs.
    hass.states.async_set("media_player.tv", "idle")
    await hass.async_block_till_done()
    assert hass.states.get(SELECT).state == "Hanging out"
    await advance(hass, freezer, CLEAR + 1)
    assert hass.states.get(PHASE).state == "cooldown"
    await advance(hass, freezer, COOL + 1)
    assert hass.states.get(PHASE).state == "vacant"
    assert hass.states.get(SELECT).state == "unavailable"


async def test_pass_through(hass: HomeAssistant, freezer) -> None:
    await setup_space(hass)
    events = async_capture_events(hass, EVENT_TYPE)

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, PASS + 1)

    assert hass.states.get(PHASE).state == "vacant"
    assert any(event.data["type"] == "passing_through" for event in events)
    assert not any(
        event.data["type"] == "phase_changed" and event.data["to"] == "occupied"
        for event in events
    )


async def test_override_service_and_resume(hass: HomeAssistant, freezer) -> None:
    await setup_space(hass)
    await occupy(hass, freezer)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": SELECT, "option": "Watching TV"},
        blocking=True,
    )
    select_state = hass.states.get(SELECT)
    assert select_state.state == "Watching TV"
    assert select_state.attributes["override"] is True

    await hass.services.async_call(
        "button", "press", {"entity_id": RESUME}, blocking=True
    )
    assert hass.states.get(SELECT).state == "Hanging out"

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {"entity_id": SELECT, "state": "watching_tv"},
        blocking=True,
    )
    assert hass.states.get(SELECT).state == "Watching TV"

    await hass.services.async_call(
        DOMAIN, "clear_override", {"entity_id": SELECT}, blocking=True
    )
    assert hass.states.get(SELECT).state == "Hanging out"


async def test_control_wakes_vacant_space(hass: HomeAssistant, freezer) -> None:
    await setup_space(hass)
    assert hass.states.get(PHASE).state == "vacant"

    # A press type with no binding does nothing.
    hass.states.async_set(
        "event.remote", "2026-01-01T00:00:02.000+00:00", {"event_type": "double"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "vacant"

    hass.states.async_set(
        "event.remote", "2026-01-01T00:00:05.000+00:00", {"event_type": "single"}
    )
    await hass.async_block_till_done()

    assert hass.states.get(PHASE).state == "occupied"
    select_state = hass.states.get(SELECT)
    assert select_state.state == "Watching TV"
    assert select_state.attributes["override"] is True


async def test_adopts_existing_presence_on_startup(
    hass: HomeAssistant, freezer
) -> None:
    enter_events = async_capture_events(hass, "test_hangout_enter")
    hass.states.async_set("binary_sensor.motion", "on")
    hass.states.async_set("media_player.tv", "idle")
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Adopted as occupied without replaying any actions.
    assert hass.states.get(PHASE).state == "occupied"
    assert hass.states.get(SELECT).state == "Hanging out"
    assert len(enter_events) == 0
