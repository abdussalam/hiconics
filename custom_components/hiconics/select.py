"""Select platform for Hiconics TOU mode configuration."""

import logging
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MODE_OPTIONS = [
    "0 - Hold / Self Use",
    "1 - Charge",
    "2 - Discharge",
]

MODE_MAP_TO_NUM = {
    "0 - Hold / Self Use": "0",
    "1 - Charge": "1",
    "2 - Discharge": "2",
}

MODE_MAP_TO_TXT = {
    "0": "0 - Hold / Self Use",
    "1": "1 - Charge",
    "2": "2 - Discharge",
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    for slot in range(1, 7):
        base_reg = 40 + ((slot - 1) * 6)
        entities.append(HiconicsTouModeSelect(coordinator, api, entry, slot, f"C{base_reg+2}"))

    async_add_entities(entities)


class HiconicsTouModeSelect(CoordinatorEntity, SelectEntity):
    """Interactive mode select control for TOU slots."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = MODE_OPTIONS

    def __init__(self, coordinator, api, entry, slot: int, reg_key: str):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._slot = slot
        self._reg_key = reg_key
        self._attr_name = f"TOU Slot {slot} Mode"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_{reg_key}"

    @property
    def device_info(self):
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str:
        raw = str(self.coordinator.extra_data.get(self._reg_key, "0"))
        return MODE_MAP_TO_TXT.get(raw, "0 - Hold / Self Use")

    async def async_select_option(self, option: str) -> None:
        num_val = MODE_MAP_TO_NUM.get(option, "0")
        base_reg = 40 + ((self._slot - 1) * 6)

        current_map = {
            f"C{base_reg}": self.coordinator.extra_data.get(f"C{base_reg}", "0000"),
            f"C{base_reg+1}": self.coordinator.extra_data.get(f"C{base_reg+1}", "0000"),
            f"C{base_reg+2}": self.coordinator.extra_data.get(f"C{base_reg+2}", "0"),
            f"C{base_reg+3}": self.coordinator.extra_data.get(f"C{base_reg+3}", "25"),
            f"C{base_reg+4}": self.coordinator.extra_data.get(f"C{base_reg+4}", "100"),
            f"C{base_reg+5}": self.coordinator.extra_data.get(f"C{base_reg+5}", "18"),
        }
        current_map[self._reg_key] = num_val

        params = {k: {"v": v} for k, v in current_map.items()}
        _LOGGER.info("Updating TOU Slot %s mode to %s (%s)...", self._slot, option, num_val)
        await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        self.coordinator.update_extra_data(current_map)
