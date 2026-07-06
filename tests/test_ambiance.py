"""Shared-ambiance rules: the open-floor-plan kitchen next to a movie."""

from datetime import timedelta

from homeassistant.core import Context, HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.labs_experience.const import DOMAIN

WAKE = 10
CLEAR = 30
PASS = 5
COOL = 15

PHASE = "sensor.kitchen_phase"
SELECT = "select.kitchen_experience"
LIVING = "select.living_room_experience"
EVENING = "2026-07-05 20:00:00+00:00"


def make_kitchen() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen",
        data={"name": "Kitchen"},
        options={
            "presence_entities": ["binary_sensor.kitchen_occupancy"],
            "wake_duration": WAKE,
            "clear_delay": CLEAR,
            "pass_through_delay": PASS,
            "cooldown_duration": COOL,
            "lights_ambient": ["light.counter", "light.island"],
            "lights_night": ["light.toe_kick"],
            "states": [],
            "ambiance_rules": [
                {
                    "id": "living_media",
                    "entity_id": LIVING,
                    "states": "media",
                    "priority": 10,
                    "brightness_cap": 25,
                    "vacant_brightness": 10,
                    "wake_brightness": 15,
                },
            ],
        },
    )


async def setup_kitchen(hass: HomeAssistant) -> MockConfigEntry:
    await hass.config.async_set_time_zone("UTC")
    hass.states.async_set("binary_sensor.kitchen_occupancy", "off")
    hass.states.async_set(LIVING, "Hanging out")
    for entity_id in ("light.counter", "light.island", "light.toe_kick"):
        hass.states.async_set(
            entity_id, "off", {"supported_color_modes": ["color_temp"]}
        )
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 30.0})
    entry = make_kitchen()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def advance(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def calls_for(calls, entity_id):
    return [call for call in calls if entity_id in str(call.data.get("entity_id"))]


async def test_cap_applies_and_releases_live(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    await setup_kitchen(hass)

    # Cooking normally: full circadian brightness.
    hass.states.async_set("binary_sensor.kitchen_occupancy", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)
    assert calls_for(turn_on, "light.counter")[-1].data["brightness_pct"] == 100

    # A movie starts next door: the kitchen dims to the cap, live.
    hass.states.async_set(LIVING, "Media")
    await hass.async_block_till_done()
    assert calls_for(turn_on, "light.counter")[-1].data["brightness_pct"] == 25
    # The kitchen's own experience did not change.
    assert hass.states.get(SELECT).state == "Occupied"

    # Movie ends: brightness restores as it was before.
    hass.states.async_set(LIVING, "Hanging out")
    await hass.async_block_till_done()
    assert calls_for(turn_on, "light.counter")[-1].data["brightness_pct"] == 100


async def test_vacant_glow_follows_the_movie(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    await setup_kitchen(hass)
    assert hass.states.get(PHASE).state == "vacant"

    # Movie starts while the kitchen is empty: toe-kick glow, not darkness.
    hass.states.async_set(LIVING, "Media")
    await hass.async_block_till_done()
    glow = calls_for(turn_on, "light.toe_kick")
    assert glow and glow[-1].data["brightness_pct"] == 10
    assert calls_for(turn_off, "light.counter")

    # Movie ends: the glow goes out.
    before_off = len(turn_off)
    hass.states.async_set(LIVING, "Hanging out")
    await hass.async_block_till_done()
    assert len(turn_off) > before_off


async def test_wake_brightness_override(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    await setup_kitchen(hass)

    hass.states.async_set(LIVING, "Media")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.kitchen_occupancy", "on")
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "waking"
    wake = calls_for(turn_on, "light.toe_kick")[-1]
    assert wake.data["brightness_pct"] == 15


async def test_manual_authority_beats_ambiance(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    await setup_kitchen(hass)

    hass.states.async_set("binary_sensor.kitchen_occupancy", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)

    # Human takes the kitchen lights.
    hass.states.async_set(
        "light.counter",
        "on",
        {"supported_color_modes": ["color_temp"]},
        context=Context(),
    )
    await hass.async_block_till_done()
    assert hass.states.get("select.kitchen_lighting").state == "manual"

    # Movie starting must not dim a manually-controlled kitchen.
    count = len(turn_on)
    hass.states.async_set(LIVING, "Media")
    await hass.async_block_till_done()
    assert len(turn_on) == count
