"""Lighting facet: built-in defaults, circadian drift, lux gate, takeover."""

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

PHASE = "sensor.snug_phase"
SELECT = "select.snug_experience"
LIGHTING = "select.snug_lighting"

EVENING = "2026-07-05 20:00:00+00:00"
NOON = "2026-07-06 12:00:00+00:00"


def make_snug(**extra) -> MockConfigEntry:
    options = {
        "presence_entities": ["binary_sensor.motion"],
        "wake_duration": WAKE,
        "clear_delay": CLEAR,
        "pass_through_delay": PASS,
        "cooldown_duration": COOL,
        "lights_ambient": ["light.main"],
        "lights_night": ["light.nightstrip"],
        "states": [],
        **extra,
    }
    return MockConfigEntry(
        domain=DOMAIN, title="Snug", data={"name": "Snug"}, options=options
    )


async def setup_snug(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config.async_set_time_zone("UTC")
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set(
        "light.main", "off", {"supported_color_modes": ["color_temp"]}
    )
    hass.states.async_set(
        "light.nightstrip", "off", {"supported_color_modes": ["brightness"]}
    )
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 30.0})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def advance(hass: HomeAssistant, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def calls_for(calls, entity_id):
    return [
        call for call in calls if entity_id in str(call.data.get("entity_id"))
    ]


async def test_default_lighting_through_the_evening(
    hass: HomeAssistant, freezer
) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    await setup_snug(hass, make_snug())

    # Walk in: the night strip acknowledges you, gently.
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "waking"
    wake_calls = calls_for(turn_on, "light.nightstrip")
    assert wake_calls and wake_calls[0].data["brightness_pct"] == 20

    # Fully occupied: ambient comes up on the circadian curve
    # (sun elevation 30 => full day: max kelvin and brightness).
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(PHASE).state == "occupied"
    baseline = calls_for(turn_on, "light.main")
    assert baseline
    assert baseline[-1].data["color_temp_kelvin"] == 5500
    # The baseline is exclusive: the night strip is released.
    assert calls_for(turn_off, "light.nightstrip")

    # Leave: cool-down dims, vacancy turns everything off.
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, CLEAR + 1)
    assert hass.states.get(PHASE).state == "cooldown"
    await advance(hass, freezer, COOL + 1)
    assert hass.states.get(PHASE).state == "vacant"
    assert calls_for(turn_off, "light.main")


async def test_lux_gate_blocks_bright_rooms(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = make_snug(illuminance_sensor="sensor.lux", lux_threshold=50)
    hass.states.async_set("sensor.lux", "400")
    await setup_snug(hass, entry)

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(PHASE).state == "occupied"
    assert not turn_on


async def test_circadian_drift_and_takeover(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    await setup_snug(hass, make_snug())

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(PHASE).state == "occupied"

    # Reflect our own command as the light turning on, using our context —
    # this must NOT count as a manual takeover.
    own_context = calls_for(turn_on, "light.main")[-1].context
    hass.states.async_set(
        "light.main",
        "on",
        {"supported_color_modes": ["color_temp"]},
        context=own_context,
    )
    await hass.async_block_till_done()
    assert hass.states.get(LIGHTING).state == "auto"

    # The sun sets; the next tick warms the room.
    hass.states.async_set("sun.sun", "below_horizon", {"elevation": -6.0})
    before = len(calls_for(turn_on, "light.main"))
    await advance(hass, freezer, 360)
    drift = calls_for(turn_on, "light.main")[before:]
    assert drift and drift[-1].data["color_temp_kelvin"] == 2200

    # A human hits the wall switch: lighting goes manual, the experience
    # state does not move, and the engine stops touching lights.
    hass.states.async_set(
        "light.main",
        "off",
        {"supported_color_modes": ["color_temp"]},
        context=Context(),
    )
    await hass.async_block_till_done()
    assert hass.states.get(LIGHTING).state == "manual"
    assert hass.states.get(SELECT).state == "Occupied"
    count = len(turn_on)
    await advance(hass, freezer, 360)  # tick must not adjust anything
    assert len(turn_on) == count

    # Vacancy releases manual control.
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, CLEAR + 1)
    await advance(hass, freezer, COOL + 1)
    assert hass.states.get(PHASE).state == "vacant"
    assert hass.states.get(LIGHTING).state == "auto"


async def test_target_lux_compensation(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = make_snug(illuminance_sensor="sensor.lux", target_lux=200)
    hass.states.async_set("sensor.lux", "50")
    await setup_snug(hass, entry)

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(PHASE).state == "occupied"

    # Initial brightness estimated from the deficit:
    # (200-50)/200 = 0.75 -> 35 + 0.75 * 65 = 84%.
    baseline = calls_for(turn_on, "light.main")[-1]
    assert baseline.data["brightness_pct"] == 84

    # Reflect the light as on (our own context: no takeover).
    hass.states.async_set(
        "light.main",
        "on",
        {"supported_color_modes": ["color_temp"]},
        context=baseline.context,
    )
    await hass.async_block_till_done()

    # Afternoon sun floods the room: the loop dims, bounded to -20%.
    hass.states.async_set("sensor.lux", "400")
    await hass.async_block_till_done()
    adjustments = [
        call for call in turn_on if "brightness_step_pct" in call.data
    ]
    assert adjustments and adjustments[-1].data["brightness_step_pct"] == -20

    # A second reading right away is rate-limited: no oscillation.
    hass.states.async_set("sensor.lux", "500")
    await hass.async_block_till_done()
    assert (
        len([call for call in turn_on if "brightness_step_pct" in call.data]) == 1
    )


async def test_lux_loop_runs_for_fixed_color_states(
    hass: HomeAssistant, freezer
) -> None:
    """Target-lux compensation must tick even when the state color is fixed."""
    freezer.move_to(EVENING)
    turn_on = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = make_snug(
        illuminance_sensor="sensor.lux",
        target_lux=200,
        states=[
            {"id": "warm_room", "name": "Warm room", "priority": 0,
             "light_roles": ["ambient"], "light_color": "warm"},
        ],
    )
    hass.states.async_set("sensor.lux", "50")
    await setup_snug(hass, entry)

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(SELECT).state == "Warm room"

    baseline = calls_for(turn_on, "light.main")[-1]
    assert baseline.data["color_temp_kelvin"] == 2700  # fixed warm
    hass.states.async_set(
        "light.main",
        "on",
        {"supported_color_modes": ["color_temp"]},
        context=baseline.context,
    )
    await hass.async_block_till_done()

    # Still 150 lx short of target: the next tick brightens (bounded +20%).
    await advance(hass, freezer, 360)
    adjustments = [call for call in turn_on if "brightness_step_pct" in call.data]
    assert adjustments and adjustments[-1].data["brightness_step_pct"] == 20


async def test_daypart_gated_states(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(EVENING)
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    entry = make_snug(
        states=[
            {"id": "unwind", "name": "Unwind", "priority": 10,
             "dayparts": ["evening", "night"]},
            {"id": "daylife", "name": "Daylife", "priority": 0},
        ]
    )
    await setup_snug(hass, entry)

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, WAKE + 1)
    assert hass.states.get(SELECT).state == "Unwind"

    # Noon the next day: the evening state no longer matches.
    freezer.move_to(NOON)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.snug_daypart").state == "day"
    assert hass.states.get(SELECT).state == "Daylife"
