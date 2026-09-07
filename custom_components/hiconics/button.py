"""Button platform for Hiconics integration."""

import json
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics buttons from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    buttons = [
        HiconicsReadButton(coordinator, api, entry, "tou", "Read TOU Settings", "r_A8", "C32"),
        HiconicsReadButton(coordinator, api, entry, "mode", "Read Inverter Mode", "r_A1", "C1"),
        HiconicsReadButton(coordinator, api, entry, "battery", "Read Battery Settings", "r_A6", "C32"),
    ]
    async_add_entities(buttons)


class HiconicsReadButton(ButtonEntity):
    """Representation of a button to trigger a read command to the inverter."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, entry, read_type, name, code, param_key):
        """Initialize the button."""
        self.coordinator = coordinator
        self.api = api
        self.entry = entry
        self._read_type = read_type
        self._attr_name = name
        self._code = code
        self._param_key = param_key
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_{read_type}"

    @property
    def device_info(self):
        """Link to the Inverter device."""
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            res = await self.api.async_send_command(
                code=self._code,
                operation_type=4,
                input_param={self._param_key: {"v": "1"}},
            )
            analysis_raw = res.get("analysisResult")
            if analysis_raw:
                parsed = json.loads(analysis_raw) if isinstance(analysis_raw, str) else analysis_raw
                if isinstance(parsed, dict):
                    self.coordinator.update_extra_data(parsed)
                    _LOGGER.info("Successfully fetched %s registers.", self._read_type)
        except Exception as err:
            _LOGGER.error("Failed to read settings %s: %s", self._read_type, err)
