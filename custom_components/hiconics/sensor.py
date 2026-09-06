"""Sensor platform for Hiconics inverter and battery."""

import logging
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DIAGNOSTIC_KEYWORDS = [
    "status", "state", "mode", "alarm", "warning", "error", "version",
    "sn", "supplier", "record", "control", "type", "clusters", "parm",
    "factor", "system time", "rated", "capacity", "setting", "limit",
    "sampling sections", "fault level", "flag"
]

BATTERY_KEYWORDS = ["battery", "inline", "parallel", "charg", "soc", "b_c", "capacity"]


def is_battery_sensor(key: str, name: str) -> bool:
    lower = f"{key} {name or ''}".lower()
    return any(w in lower for w in BATTERY_KEYWORDS)


def get_entity_category(key: str, name: str):
    lower = f"{key} {name or ''}".lower()
    if any(w in lower for w in DIAGNOSTIC_KEYWORDS):
        return EntityCategory.DIAGNOSTIC
    return None


def normalize_unit(unit: str) -> str:
    if not unit:
        return None
    units_map = {"KW": "kW", "HZ": "Hz", "℃": "°C", "Var": "var"}
    return units_map.get(unit, unit)


def get_device_class(unit: str):
    mapping = {
        "V": SensorDeviceClass.VOLTAGE,
        "mV": SensorDeviceClass.VOLTAGE,
        "A": SensorDeviceClass.CURRENT,
        "W": SensorDeviceClass.POWER,
        "kW": SensorDeviceClass.POWER,
        "kvar": SensorDeviceClass.REACTIVE_POWER,
        "var": SensorDeviceClass.REACTIVE_POWER,
        "kVA": SensorDeviceClass.APPARENT_POWER,
        "kWh": SensorDeviceClass.ENERGY,
        "%": SensorDeviceClass.BATTERY,
        "Hz": SensorDeviceClass.FREQUENCY,
        "°C": SensorDeviceClass.TEMPERATURE,
        "s": SensorDeviceClass.DURATION,
    }
    return mapping.get(unit)


def get_state_class(unit: str, key: str, name: str):
    lower = f"{key} {name or ''}".lower()
    if unit in ["w", "kw", "kva", "kvar", "var", "v", "mv", "a", "hz", "%", "°c", "s"]:
        return SensorStateClass.MEASUREMENT
    if unit == "kwh" and "total" in lower:
        return SensorStateClass.TOTAL_INCREASING
    if unit == "kwh":
        return SensorStateClass.TOTAL
    return None


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics sensors from entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    known_keys = set()

    def _create_entities():
        new_entities = []
        data = coordinator.data or {}
        data_list = data.get("dataList", [])

        for item in data_list:
            key = item.get("key")
            if not key or key in known_keys:
                continue

            known_keys.add(key)
            new_entities.append(HiconicsSensor(coordinator, entry, item))

        if new_entities:
            async_add_entities(new_entities)

    _create_entities()
    entry.async_on_unload(coordinator.async_add_listener(_create_entities))


class HiconicsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Hiconics Sensor."""

    def __init__(self, coordinator, entry, item):
        super().__init__(coordinator)
        self.entry = entry
        self._key = item.get("key")
        self._raw_name = item.get("name") or self._key
        self._attr_unique_id = f"hiconics_{entry.entry_id}_{self._key}"
        self._attr_name = f"Hiconics {self._raw_name}"

        # Assign Device Association (Inverter vs Battery)
        self._is_battery = is_battery_sensor(self._key, self._raw_name)

        # Attribute definitions
        unit = normalize_unit(item.get("unit"))
        if not unit and any(x in self._raw_name.lower() for x in ["soc", "soh"]):
            unit = "%"

        self._attr_native_unit_of_measurement = unit
        if unit:
            self._attr_device_class = get_device_class(unit)
            self._attr_state_class = get_state_class(unit.lower(), self._key, self._raw_name)

        self._attr_entity_category = get_entity_category(self._key, self._raw_name)

    @property
    def device_info(self):
        inverter_device = {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

        if self._is_battery:
            return {
                "identifiers": {(DOMAIN, f"{self.entry.entry_id}_battery")},
                "manufacturer": "Hiconics",
                "model": "LFP Battery",
                "name": "Hiconics Battery",
                "via_device": (DOMAIN, f"{self.entry.entry_id}_inverter"),
            }
        return inverter_device

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        data_list = self.coordinator.data.get("dataList", [])
        for item in data_list:
            if item.get("key") == self._key:
                val = item.get("value")
                if val is None or val == "":
                    return None
                try:
                    return float(val) if "." in str(val) else int(val)
                except ValueError:
                    return str(val)
        return None
