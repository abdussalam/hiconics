"""Number platform for Hiconics TOU Amps, SOC limits, and Grid Power Limit."""

import logging
from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BATTERY_CONFIG_MAP = {
    "C33": {"name": "On-Grid Min Cut-off SOC", "unit": "%", "min": 0, "max": 50, "step": 1},
    "C34": {"name": "On-Grid Max Target SOC", "unit": "%", "min": 50, "max": 100, "step": 1},
    "C35": {"name": "On-Grid Hysteresis", "unit": "%", "min": 0, "max": 30, "step": 1},
    "C36": {"name": "Off-Grid Min Cut-off SOC", "unit": "%", "min": 0, "max": 50, "step": 1},
    "C37": {"name": "Off-Grid Max Target SOC", "unit": "%", "min": 50, "max": 100, "step": 1},
    "C38": {"name": "Off-Grid Hysteresis", "unit": "%", "min": 0, "max": 30, "step": 1},
    "C217": {"name": "Grid Power Limit", "unit": "W", "min": 0, "max": 15000, "step": 1},
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []

    for slot in range(1, 7):
        base_reg = 40 + ((slot - 1) * 6)
        entities.append(
            HiconicsTouNumber(
                coordinator, api, entry, slot, f"C{base_reg+3}", "D. Max Amps", "A", 0.0, 25.0, step=0.1
            )
        )
        entities.append(
            HiconicsTouNumber(
                coordinator, api, entry, slot, f"C{base_reg+4}", "E. Max SOC", "%", 50.0, 100.0, step=1.0
            )
        )
        entities.append(
            HiconicsTouNumber(
                coordinator, api, entry, slot, f"C{base_reg+5}", "F. Min SOC", "%", 0.0, 100.0, step=1.0
            )
        )

    for reg_key, config in BATTERY_CONFIG_MAP.items():
        entities.append(
            HiconicsBatteryNumber(
                coordinator, api, entry, reg_key, config["name"], config["unit"], config["min"], config["max"], step=config.get("step", 1.0)
            )
        )

    async_add_entities(entities)


class HiconicsTouNumber(CoordinatorEntity, NumberEntity):
    """Interactive number control for TOU Amps and SOC limits (local staging)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, api, entry, slot: int, reg_key: str, name_type: str, unit: str, min_v: float, max_v: float, step: float = 1.0
    ):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._slot = slot
        self._reg_key = reg_key
        self._attr_name = f"Slot {slot} - {name_type}"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_native_step = step
        self._attr_unique_id = f"hiconics_{entry.entry_id}_num_{reg_key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.extra_data.get(self._reg_key)
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        base_reg = 40 + ((self._slot - 1) * 6)
        required_keys = [f"C{base_reg + i}" for i in range(6)]
        
        if not self.coordinator.extra_data or not all(k in self.coordinator.extra_data for k in required_keys):
            raise HomeAssistantError("Cannot stage value: TOU register block has not been read yet. Please click 'Pull TOU Settings' first.")

        val_str = f"{value:.1f}" if self._attr_native_step < 1.0 else str(int(value))
        
        # Stage change locally
        self.coordinator.extra_data[self._reg_key] = val_str
        self.async_write_ha_state()


class HiconicsBatteryNumber(CoordinatorEntity, NumberEntity):
    """Interactive number control for Battery Configuration and Power Limits."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, api, entry, reg_key: str, name: str, unit: str, min_v: float, max_v: float, step: float = 1.0
    ):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._reg_key = reg_key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_native_step = step
        self._attr_unique_id = f"hiconics_{entry.entry_id}_bat_num_{reg_key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.extra_data.get(self._reg_key)
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        if self._reg_key in ["C33", "C34", "C35", "C36", "C37", "C38"]:
            required_keys = ["C33", "C34", "C35", "C36", "C37", "C38"]
            if not all(k in self.coordinator.extra_data for k in required_keys):
                raise HomeAssistantError("Cannot write to inverter: Battery register block has not been read yet.")
            current_map = {k: str(self.coordinator.extra_data[k]) for k in required_keys}
            code = "s_A6"
        else:
            if self._reg_key not in self.coordinator.extra_data:
                raise HomeAssistantError(f"Cannot write to inverter: {self._reg_key} has not been read yet.")
            current_map = {self._reg_key: str(self.coordinator.extra_data[self._reg_key])}
            code = "s_A8"

        val_str = f"{value:.1f}" if self._attr_native_step < 1.0 else str(int(value))
        current_map[self._reg_key] = val_str

        params = {k: {"v": v} for k, v in current_map.items()}
        await self.api.async_send_command(code=code, operation_type=5, input_param=params)
        self.coordinator.update_extra_data(current_map)
