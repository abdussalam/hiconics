"""Button platform for Hiconics integration."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = [
        HiconicsReadSettingsButton(coordinator, api, entry),
    ]

    for slot in range(1, 7):
        entities.append(HiconicsApplyTouSlotButton(coordinator, api, entry, slot))

    async_add_entities(entities)


class HiconicsReadSettingsButton(CoordinatorEntity, ButtonEntity):
    """Button to manually force reading settings from the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Read Inverter Settings"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_read_settings"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Read TOU, mode, and battery settings from API."""
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"entry_id": self.entry.entry_id, "type": "tou"}
        )


class HiconicsApplyTouSlotButton(CoordinatorEntity, ButtonEntity):
    """Button to push staged local TOU slot changes to the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-upload"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, entry, slot: int):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._slot = slot
        self._attr_name = f"Slot {slot} - Apply Settings"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_apply_tou_{slot}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Collect staged local values for the slot block and dispatch API update."""
        base_reg = 40 + ((self._slot - 1) * 6)
        required_keys = [f"C{base_reg + i}" for i in range(6)]

        if not all(k in self.coordinator.extra_data for k in required_keys):
            raise HomeAssistantError("Cannot apply settings: Register block has not been read yet.")

        payload = {
            "entry_id": self.entry.entry_id,
            "slot": self._slot,
            "start_time": str(self.coordinator.extra_data[f"C{base_reg}"]),
            "end_time": str(self.coordinator.extra_data[f"C{base_reg+1}"]),
            "mode": str(self.coordinator.extra_data[f"C{base_reg+2}"]),
            "max_amps": str(self.coordinator.extra_data[f"C{base_reg+3}"]),
            "max_soc": str(self.coordinator.extra_data[f"C{base_reg+4}"]),
            "min_soc": str(self.coordinator.extra_data[f"C{base_reg+5}"]),
        }

        await self.hass.services.async_call(DOMAIN, "set_tou_slot", payload)
