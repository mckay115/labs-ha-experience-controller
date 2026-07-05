"""A full multi-state room, driven the way a real evening plays out."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.core import HomeAssistant

from custom_components.labs_experience.const import DOMAIN

WAKE = 10
CLEAR = 30
PASS = 5
COOL = 15

SELECT = "select.den_experience"
PHASE = "sensor.den_phase"


def make_den() -> MockConfigEntry:
    """A den with ambient baseline, work mode, and media mode."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Den",
        data={"name": "Den"},
        options={
            "presence_entities": ["binary_sensor.motion", "binary_sensor.desk_seat"],
            "wake_duration": WAKE,
            "clear_delay": CLEAR,
            "pass_through_delay": PASS,
            "cooldown_duration": COOL,
            "states": [
                {
                    "id": "ambient",
                    "name": "Ambient",
                    "priority": 0,
                    "evidence_entities": [],
                },
                {
                    "id": "work",
                    "name": "Work",
                    "priority": 10,
                    "evidence_entities": [
                        "switch.desk",
                        "binary_sensor.desk_seat",
                    ],
                    "evidence_mode": "any",
                },
                {
                    "id": "media",
                    "name": "Media",
                    "priority": 20,
                    "evidence_entities": ["media_player.tv"],
                    "active_states": "playing,buffering",
                    "hold_occupancy": True,
                },
            ],
        },
    )


async def advance(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def set_state(hass: HomeAssistant, entity_id: str, value: str) -> None:
    hass.states.async_set(entity_id, value)
    await hass.async_block_till_done()


async def test_an_evening_in_the_den(hass: HomeAssistant, freezer) -> None:
    for entity_id in (
        "binary_sensor.motion",
        "binary_sensor.desk_seat",
        "switch.desk",
    ):
        hass.states.async_set(entity_id, "off")
    hass.states.async_set("media_player.tv", "idle")
    entry = make_den()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Walk in: the room acknowledges you (standby / night-light phase).
    await set_state(hass, "binary_sensor.motion", "on")
    assert hass.states.get(PHASE).state == "waking"

    # Stay a moment: fully occupied, settles into the ambient baseline.
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(PHASE).state == "occupied"
    assert hass.states.get(SELECT).state == "Ambient"

    # Flip the desk switch: work lighting.
    await set_state(hass, "switch.desk", "on")
    assert hass.states.get(SELECT).state == "Work"

    # The TV comes on: media mode outranks work.
    await set_state(hass, "media_player.tv", "playing")
    assert hass.states.get(SELECT).state == "Media"

    # Everyone settles in: desk off, motion goes quiet. The movie holds
    # the room occupied well past the normal clear delay.
    await set_state(hass, "switch.desk", "off")
    await set_state(hass, "binary_sensor.motion", "off")
    await advance(hass, freezer, CLEAR * 3)
    assert hass.states.get(PHASE).state == "occupied"
    assert hass.states.get(SELECT).state == "Media"

    # Movie ends: back to ambient, and the clear countdown finally runs.
    await set_state(hass, "media_player.tv", "idle")
    assert hass.states.get(SELECT).state == "Ambient"
    await advance(hass, freezer, CLEAR + 1)
    assert hass.states.get(PHASE).state == "cooldown"
    await advance(hass, freezer, COOL + 1)
    assert hass.states.get(PHASE).state == "vacant"


async def test_entering_settles_straight_into_evidence_state(
    hass: HomeAssistant, freezer
) -> None:
    """Sitting down at the desk wakes the room directly into Work."""
    for entity_id in ("binary_sensor.motion", "switch.desk"):
        hass.states.async_set(entity_id, "off")
    hass.states.async_set("binary_sensor.desk_seat", "off")
    hass.states.async_set("media_player.tv", "idle")
    entry = make_den()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The desk seat is both presence and Work evidence.
    await set_state(hass, "binary_sensor.desk_seat", "on")
    assert hass.states.get(PHASE).state == "waking"
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(PHASE).state == "occupied"
    assert hass.states.get(SELECT).state == "Work"

    # Standing up falls back to Ambient; leaving vacates through cooldown.
    await set_state(hass, "binary_sensor.desk_seat", "off")
    assert hass.states.get(SELECT).state == "Ambient"
    await advance(hass, freezer, CLEAR + 1)
    assert hass.states.get(PHASE).state == "cooldown"
    await advance(hass, freezer, COOL + 1)
    assert hass.states.get(PHASE).state == "vacant"
