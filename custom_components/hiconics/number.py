"""Number platform for Hiconics TOU Amps and SOC limits."""

import logging
from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    for slot in range(1, 7):
        base_reg = 40 + ((slot - 1) * 6)
        entities.append(HiconicsTouNumber(coordinator, api, entry, slot, f"C{base_reg+3}", "D. Max Amps", "A", 1, 100))
        entities.append(HiconicsTouNumber(coordinator, api, entry, slot, f"C{base_reg+4}", "E. Max SOC", "%", 10, 100))
        entities.append(HiconicsTouNumber(coordinator, api, entry, slot, f"C{base_reg+5}", "F. Min SOC", "%", 10, 100))

    async_add_entities(entities)


class HiconicsTouNumber(CoordinatorEntity, NumberEntity):
    """Interactive number control for TOU Amps and SOC limits."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1

    def __init__(self, coordinator, api, entry, slot: int, reg_key: str, name_type: str, unit: str, min_v: float, max_v: float):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._slot = slot
        self._reg_key = reg_key
        # Strict alphabetical prefix to group tightly in UI
        self._attr_name = f"Slot {slot} - {name_type}"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_unique_id = f"hiconics_{entry.entry_id}_num_{reg_key}"

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
    def native_value(self) -> float:
        val = self.coordinator.extra_data.get(self._reg_key)
        if val is None:
            return self._attr_native_min_value
        try:
            return float(val)
        except ValueError:
            return self._attr_native_min_value

    async def async_set_native_value(self, value: float) -> None:
        int_val = str(int(value))
        base_reg = 40 + ((self._slot - 1) * 6)

        current_map = {
            f"C{base_reg}": self.coordinator.extra_data.get(f"C{base_reg}", "0000"),
            f"C{base_reg+1}": self.coordinator.extra_data.get(f"C{base_reg+1}", "0000"),
            f"C{base_reg+2}": self.coordinator.extra_data.get(f"C{base_reg+2}", "0"),
            f"C{base_reg+3}": self.coordinator.extra_data.get(f"C{base_reg+3}", "25"),
            f"C{base_reg+4}": self.coordinator.extra_data.get(f"C{base_reg+4}", "100"),
            f"C{base_reg+5}": self.coordinator.extra_data.get(f"C{base_reg+5}", "18"),
        }
        current_map[self._reg_key] = int_val

        params = {k: {"v": v} for k, v in current_map.items()}
        await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        self.coordinator.update_extra_data(current_map)
