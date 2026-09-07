"""Number platform for Hiconics TOU Amps, SOC limits, and Battery Settings."""

import logging
from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Corrected Battery Register Mapping
BATTERY_CONFIG_MAP = {
    "C32": {"name": "On Grid Min SOC", "unit": "%", "min": 0, "max": 100},
    "C33": {"name": "On Grid Max SOC", "unit": "%", "min": 0, "max": 100},
    "C34": {"name": "On Grid Hysteresis SOC", "unit": "%", "min": 0, "max": 100},
    "C35": {"name": "Off Grid Min SOC", "unit": "%", "min": 0, "max": 100},
    "C36": {"name": "Off Grid Max SOC", "unit": "%", "min": 0, "max": 100},
    "C37": {"name": "Off Grid Hysteresis SOC", "unit": "%", "min": 0, "max": 100},
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    
    # 1. TOU Number Entities
    for slot in range(1, 7):
        base_reg = 40 + ((slot - 1) * 6)
        entities.append(HiconicsTouNumber(coordinator, api, entry, slot, f"C{base_reg+3}", "D. Max Amps", "A", 1, 100))
        entities.append(HiconicsTouNumber(coordinator, api, entry, slot, f"C{base_reg+4}", "E. Max SOC", "%", 10, 100))
        entities.append(HiconicsTouNumber(coordinator, api, entry, slot, f"C{base_reg+5}", "F. Min SOC", "%", 10, 100))

    # 2. Battery Configuration Number Entities
    for reg_key, config in BATTERY_CONFIG_MAP.items():
        entities.append(
            HiconicsBatteryNumber(
                coordinator, api, entry, reg_key, config["name"], config["unit"], config["min"], config["max"]
            )
        )

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


class HiconicsBatteryNumber(CoordinatorEntity, NumberEntity):
    """Interactive number control for Battery Configuration."""
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1

    def __init__(self, coordinator, api, entry, reg_key: str, name: str, unit: str, min_v: float, max_v: float):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._reg_key = reg_key
        self._attr_name = f"Battery Config - {name}"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_unique_id = f"hiconics_{entry.entry_id}_bat_num_{reg_key}"

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

        # Reconstruct the C32-C37 block with safe default fallbacks
        current_map = {
            "C32": self.coordinator.extra_data.get("C32", "10"),
            "C33": self.coordinator.extra_data.get("C33", "100"),
            "C34": self.coordinator.extra_data.get("C34", "5"),
            "C35": self.coordinator.extra_data.get("C35", "10"),
            "C36": self.coordinator.extra_data.get("C36", "100"),
            "C37": self.coordinator.extra_data.get("C37", "5"),
        }
        current_map[self._reg_key] = int_val

        params = {k: {"v": v} for k, v in current_map.items()}
        _LOGGER.info("Updating Battery Config %s to %s...", self._reg_key, int_val)
        
        await self.api.async_send_command(code="s_A6", operation_type=5, input_param=params)
        self.coordinator.update_extra_data(current_map)
