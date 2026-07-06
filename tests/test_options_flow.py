"""The grouped options menu and the common-states quick start."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.labs_experience.const import DOMAIN


def make_den() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Den",
        data={"name": "Den"},
        options={
            "presence_entities": ["binary_sensor.motion"],
            "lights_ambient": ["light.main"],
            "media_entities": ["media_player.tv"],
            "states": [],
        },
    )


async def test_starter_states_quick_start(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("media_player.tv", "idle")
    entry = make_den()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"
    assert result["menu_options"] == [
        "basics",
        "profile_menu",
        "states_menu",
        "controls_menu",
        "phase_actions",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "states_menu"}
    )
    assert result["type"] == "menu"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_starter_states"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "templates": ["hanging_out", "media", "night_light"],
            "media_entity": "media_player.tv",
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    stored = {state["id"]: state for state in entry.options["states"]}
    assert set(stored) == {"hanging_out", "media", "night_light"}
    assert stored["media"]["evidence_entities"] == ["media_player.tv"]
    assert stored["media"]["hold_occupancy"] is True
    assert stored["night_light"]["dayparts"] == ["night"]

    # The reloaded engine offers the new experiences.
    options = hass.states.get("select.den_experience").attributes["options"]
    assert {"Hanging out", "Media", "Night light"} <= set(options)


async def test_add_custom_state_sectioned_form(hass: HomeAssistant) -> None:
    """The sectioned state form stores the same flat shape as before."""
    hass.states.async_set("binary_sensor.motion", "off")
    entry = make_den()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "states_menu"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_state"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Reading",
            "priority": 15,
            "evidence": {
                "evidence_entities": ["switch.reading_lamp"],
                "dayparts": ["evening", "night"],
                "hold_occupancy": False,
            },
            "comfort": {
                "light_roles": ["accent"],
                "light_color": "warm",
            },
            "actions": {},
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    stored = {state["id"]: state for state in entry.options["states"]}["reading"]
    assert stored["name"] == "Reading"
    assert stored["priority"] == 15
    assert stored["evidence_entities"] == ["switch.reading_lamp"]
    assert stored["dayparts"] == ["evening", "night"]
    assert stored["light_roles"] == ["accent"]
    assert stored["light_color"] == "warm"
    assert "evidence" not in stored


async def test_starter_media_requires_player(hass: HomeAssistant) -> None:
    entry = make_den()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "states_menu"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_starter_states"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"templates": ["media"]}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "media_entity_required"}
