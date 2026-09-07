"""Button platform for Hiconics manual data polling."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entities = [
        HiconicsReadButton(coordinator, entry, "mode", "Pull Inverter Mode"),
        HiconicsReadButton(coordinator, entry, "battery", "Pull Battery Settings"),
        HiconicsReadButton(coordinator, entry, "tou", "Pull TOU Settings"),
    ]
    async_add_entities(entities)

class HiconicsReadButton(ButtonEntity):
    """Button to manually trigger setting reads."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, setting_type: str, name: str):
        self.coordinator = coordinator
        self.entry = entry
        self._setting_type = setting_type
        self._attr_name = name
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_read_{setting_type}"

    @property
    def device_info(self):
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Handle the button press by calling the read_settings service."""
        _LOGGER.info("Manual button pressed: %s", self._attr_name)
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"type": self._setting_type}, blocking=False
        )
