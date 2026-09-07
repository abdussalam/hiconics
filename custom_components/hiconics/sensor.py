"""Sensor platform for Hiconics inverter and battery."""

import logging
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
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


def get_clean_entity_name(raw_name: str, key: str, is_battery: bool) -> str:
    """Format a clean entity name without duplicate brand/device prefixes."""
    name = raw_name or key

    # TOU register mapping (C40 through C75)
    if key.startswith("C") and key[1:].isdigit():
        reg_num = int(key[1:])
        if 40 <= reg_num <= 75:
            slot = ((reg_num - 40) // 6) + 1
            offset = (reg_num - 40) % 6
            param_names = [
                "Start Time",
                "End Time",
                "Mode",
                "Max Charge Amps",
                "Max SOC",
                "Min SOC",
            ]
            return f"TOU Slot {slot} {param_names[offset]}"

    clean = name.strip()
    prefixes = ["hiconics battery ", "hiconics inverter ", "hiconics "]
    for prefix in prefixes:
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):].strip()
            break

    if is_battery and clean.lower().startswith("battery "):
        clean = clean[8:].strip()
    elif not is_battery and clean.lower().startswith("inverter "):
        clean = clean[9:].strip()

    return (clean or name).strip()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics sensors from entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    known_keys = set()

    def _create_entities():
        new_entities = []

        # 1. Standard polling telemetry
        data = coordinator.data or {}
        data_list = data.get("dataList", [])

        for item in data_list:
            key = item.get("key")
            if not key or key in known_keys:
                continue
            known_keys.add(key)
            new_entities.append(HiconicsSensor(coordinator, entry, item))

        # 2. On-demand extra data (e.g. TOU registers, inverter modes)
        extra_data = getattr(coordinator, "extra_data", {})
        for key in extra_data:
            if not key or key in known_keys:
                continue
            known_keys.add(key)
            new_entities.append(HiconicsExtraSensor(coordinator, entry, key))

        if new_entities:
            async_add_entities(new_entities)

    _create_entities()
    entry.async_on_unload(coordinator.async_add_listener(_create_entities))


class HiconicsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Hiconics Telemetry Sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, item):
        super().__init__(coordinator)
        self.entry = entry
        self._key = item.get("key")
        raw_name = item.get("name") or self._key
        self._attr_unique_id = f"hiconics_{entry.entry_id}_{self._key}"

        self._is_battery = is_battery_sensor(self._key, raw_name)
        self._attr_name = get_clean_entity_name(raw_name, self._key, self._is_battery)

        unit = normalize_unit(item.get("unit"))
        if not unit and any(x in raw_name.lower() for x in ["soc", "soh"]):
            unit = "%"

        self._attr_native_unit_of_measurement = unit
        if unit:
            self._attr_device_class = get_device_class(unit)
            self._attr_state_class = get_state_class(unit.lower(), self._key, raw_name)

        self._attr_entity_category = get_entity_category(self._key, raw_name)

    @property
    def device_info(self):
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")

        if self._is_battery:
            via_device_id = dr.async_get_device_id_by_identifier(
                self.hass,
                inverter_id,
                config_entry_id=self.entry.entry_id,
            )
            return {
                "identifiers": {(DOMAIN, f"{self.entry.entry_id}_battery")},
                "manufacturer": "Hiconics",
                "model": "LFP Battery",
                "name": "Hiconics Battery",
                "via_device_id": via_device_id,
            }

        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

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


class HiconicsExtraSensor(CoordinatorEntity, SensorEntity):
    """Representation of an on-demand pulled Hiconics sensor (e.g. TOU registers)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key: str):
        super().__init__(coordinator)
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"hiconics_{entry.entry_id}_extra_{key}"

        self._is_battery = False
        self._attr_name = get_clean_entity_name(key, key, self._is_battery)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        if key.startswith("C") and key[1:].isdigit():
            reg_num = int(key[1:])
            if 40 <= reg_num <= 75:
                offset = (reg_num - 40) % 6
                if offset == 3:  # Max Amps
                    self._attr_native_unit_of_measurement = "A"
                    self._attr_device_class = SensorDeviceClass.CURRENT
                    self._attr_state_class = SensorStateClass.MEASUREMENT
                elif offset in (4, 5):  # Max/Min SOC
                    self._attr_native_unit_of_measurement = "%"
                    self._attr_device_class = SensorDeviceClass.BATTERY
                    self._attr_state_class = SensorStateClass.MEASUREMENT

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
    def native_value(self):
        val = self.coordinator.extra_data.get(self._key)
        if val is None:
            return None

        # Format TOU mode registers
        if self._key.startswith("C") and self._key[1:].isdigit():
            reg_num = int(self._key[1:])
            if 40 <= reg_num <= 75 and (reg_num - 40) % 6 == 2:
                mode_map = {"0": "Hold / Self-Use", "1": "Charge", "2": "Discharge"}
                return mode_map.get(str(val), str(val))

        return val
