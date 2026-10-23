"""Text platform for Hiconics TOU time configuration."""

import logging
from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
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
        entities.append(HiconicsTouTimeText(coordinator, api, entry, slot, f"C{base_reg}", "A. Start Time"))
        entities.append(HiconicsTouTimeText(coordinator, api, entry, slot, f"C{base_reg+1}", "B. End Time"))

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
        self._attr_name = f"Slot {slot} - {name_type}"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_txt_{reg_key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self) -> str | None:
        raw = self.coordinator.extra_data.get(self._reg_key)
        if raw is None:
            return None
        raw_str = str(raw).zfill(4)
        if len(raw_str) == 4 and raw_str.isdigit():
            return f"{raw_str[:2]}:{raw_str[2:]}"
        return str(raw)

    async def async_set_value(self, value: str) -> None:
        base_reg = 40 + ((self._slot - 1) * 6)
        required_keys = [f"C{base_reg + i}" for i in range(6)]

        if not all(k in self.coordinator.extra_data for k in required_keys):
            raise HomeAssistantError("Cannot write to inverter: TOU register block has not been read yet.")

        clean_val = value.replace(":", "").zfill(4)
        current_map = {k: str(self.coordinator.extra_data[k]) for k in required_keys}
        current_map[self._reg_key] = clean_val

        params = {k: {"v": v} for k, v in current_map.items()}
        await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        self.coordinator.update_extra_data(current_map)
