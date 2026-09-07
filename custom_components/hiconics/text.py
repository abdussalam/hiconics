"""Text platform for Hiconics TOU time configuration."""

import logging
from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics text entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    for slot in range(1, 7):
        base_reg = 40 + ((slot - 1) * 6)
        entities.append(HiconicsTouTimeText(coordinator, api, entry, slot, f"C{base_reg}", "Start Time"))
        entities.append(HiconicsTouTimeText(coordinator, api, entry, slot, f"C{base_reg+1}", "End Time"))

    async_add_entities(entities)


class HiconicsTouTimeText(CoordinatorEntity, TextEntity):
    """Interactive text control for TOU Slot Start/End times."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_pattern = r"^([0-1][0-9]|2[0-3]):?[0-5][0-9]$"

    def __init__(self, coordinator, api, entry, slot: int, reg_key: str, name_type: str):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._slot = slot
        self._reg_key = reg_key
        self._attr_name = f"TOU Slot {slot} {name_type}"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_txt_{reg_key}"

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
    def native_value(self) -> str:
        raw = self.coordinator.extra_data.get(self._reg_key, "0000")
        raw_str = str(raw).zfill(4)
        if len(raw_str) == 4 and raw_str.isdigit():
            return f"{raw_str[:2]}:{raw_str[2:]}"
        return str(raw)

    async def async_set_value(self, value: str) -> None:
        clean_val = value.replace(":", "").zfill(4)
        base_reg = 40 + ((self._slot - 1) * 6)

        current_map = {
            f"C{base_reg}": self.coordinator.extra_data.get(f"C{base_reg}", "0000"),
            f"C{base_reg+1}": self.coordinator.extra_data.get(f"C{base_reg+1}", "0000"),
            f"C{base_reg+2}": self.coordinator.extra_data.get(f"C{base_reg+2}", "0"),
            f"C{base_reg+3}": self.coordinator.extra_data.get(f"C{base_reg+3}", "25"),
            f"C{base_reg+4}": self.coordinator.extra_data.get(f"C{base_reg+4}", "100"),
            f"C{base_reg+5}": self.coordinator.extra_data.get(f"C{base_reg+5}", "18"),
        }
        current_map[self._reg_key] = clean_val

        params = {k: {"v": v} for k, v in current_map.items()}
        _LOGGER.info("Updating TOU Slot %s time %s to %s...", self._slot, self._reg_key, clean_val)
        await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        self.coordinator.update_extra_data(current_map)
