"""Climate facet: comfort intents, window pause, vacancy setback."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant.core import HomeAssistant

from custom_components.labs_experience.const import DOMAIN

WAKE = 5
CLEAR = 20
PASS = 5
COOL = 5
WINDOW_DELAY = 60

PHASE = "sensor.study_phase"
SELECT = "select.study_experience"


def make_study() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Study",
        data={"name": "Study"},
        options={
            "presence_entities": ["binary_sensor.motion"],
            "wake_duration": WAKE,
            "clear_delay": CLEAR,
            "pass_through_delay": PASS,
            "cooldown_duration": COOL,
            "climate_entities": ["climate.study"],
            "window_sensors": ["binary_sensor.window"],
            "window_pause_delay": WINDOW_DELAY,
            "comfort_temp": 21.5,
            "eco_temp": 16.0,
            "vacant_climate": "eco",
            "states": [
                {"id": "cozy", "name": "Cozy", "priority": 0,
                 "climate_intent": "comfort"},
            ],
        },
    )


async def setup_study(hass: HomeAssistant) -> MockConfigEntry:
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("binary_sensor.window", "off")
    hass.states.async_set("climate.study", "heat", {"temperature": 20.0})
    entry = make_study()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def advance(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_comfort_window_pause_and_vacancy_eco(
    hass: HomeAssistant, freezer
) -> None:
    set_temp = async_mock_service(hass, "climate", "set_temperature")
    turn_off = async_mock_service(hass, "climate", "turn_off")
    set_mode = async_mock_service(hass, "climate", "set_hvac_mode")
    await setup_study(hass)

    # Occupied in Cozy: comfort temperature applies.
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(SELECT).state == "Cozy"
    assert set_temp and set_temp[-1].data["temperature"] == 21.5

    # A window opens and stays open: climate pauses, saving what it found.
    hass.states.async_set("binary_sensor.window", "on")
    await hass.async_block_till_done()
    assert not turn_off  # not yet — the delay debounces brief airing
    await advance(hass, freezer, WINDOW_DELAY + 1)
    assert turn_off

    # Window closes: prior mode and target come back.
    hass.states.async_set("binary_sensor.window", "off")
    await hass.async_block_till_done()
    assert set_mode and set_mode[-1].data["hvac_mode"] == "heat"
    assert set_temp[-1].data["temperature"] == 20.0

    # Everyone leaves: eco setback.
    count = len(set_temp)
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, CLEAR + 1)
    await advance(hass, freezer, COOL + 1)
    assert hass.states.get(PHASE).state == "vacant"
    assert len(set_temp) > count
    assert set_temp[-1].data["temperature"] == 16.0
