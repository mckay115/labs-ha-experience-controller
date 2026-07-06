"""The Spaces sidebar panel registers with the first space and unregisters
with the last."""

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.labs_experience.const import DOMAIN


async def test_panel_lifecycle(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.motion", "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Den",
        data={"name": "Den"},
        options={"presence_entities": ["binary_sensor.motion"], "states": []},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    panels = hass.data.get(frontend.DATA_PANELS, {})
    assert "labs-spaces" in panels

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    panels = hass.data.get(frontend.DATA_PANELS, {})
    assert "labs-spaces" not in panels
