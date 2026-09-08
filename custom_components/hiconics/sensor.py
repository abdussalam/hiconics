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
    name = raw_name or key
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
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    known_keys = set()

    def _create_entities():
        new_entities = []

        data = coordinator.data or {}
        data_list = data.get("dataList", [])

        # 1. Standard telemetry sensors
        for item in data_list:
            key = item.get("key")
            if not key or key in known_keys:
                continue
            known_keys.add(key)
            new_entities.append(HiconicsSensor(coordinator, entry, item))

        # 2. TOU Slot Time Sensors (Slots 1 to 6)
        for slot in range(1, 7):
            start_key = f"tou_slot_{slot}_start"
            if start_key not in known_keys:
                known_keys.add(start_key)
                new_entities.append(HiconicsTOUTimeSensor(coordinator, entry, slot, is_start=True))
            end_key = f"tou_slot_{slot}_end"
            if end_key not in known_keys:
                known_keys.add(end_key)
                new_entities.append(HiconicsTOUTimeSensor(coordinator, entry, slot, is_start=False))

        # 3. Dynamic extra registers
        extra_data = getattr(coordinator, "extra_data", {})
        controlled_keys = {"C1", "C32", "C33", "C34", "C35", "C36", "C37", "C38", "C216", "C217"}

        for key in extra_data:
            if not key or key in known_keys or key in controlled_keys:
                continue
            if key.startswith("C") and key[1:].isdigit() and 40 <= int(key[1:]) <= 76:
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
                self.hass, inverter_id, config_entry_id=self.entry.entry_id
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
        for item in self.coordinator.data.get("dataList", []):
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
    """Representation of an on-demand pulled Hiconics sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key: str):
        super().__init__(coordinator)
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"hiconics_{entry.entry_id}_extra_{key}"
        self._is_battery = False
        self._attr_name = get_clean_entity_name(key, key, self._is_battery)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
        extra = getattr(self.coordinator, "extra_data", {})
        return extra.get(self._key)


class HiconicsTOUTimeSensor(CoordinatorEntity, SensorEntity):
    """Read-only sensor for TOU Start and End Times."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, slot: int, is_start: bool):
        super().__init__(coordinator)
        self.entry = entry
        self._slot = slot

        # Slot 1 starts at C40, Slot 2 at C46, etc.
        base_reg = 40 + ((slot - 1) * 6)
        self._reg = f"C{base_reg}" if is_start else f"C{base_reg + 1}"

        time_type = "Start" if is_start else "End"
        self._attr_name = f"TOU Slot {slot} {time_type} Time"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_tou_{slot}_{time_type.lower()}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self):
        """Fetch the value from coordinator.extra_data and format as HH:MM."""
        extra_data = getattr(self.coordinator, "extra_data", {})
        raw_time = extra_data.get(self._reg)
        if raw_time and str(raw_time) != "None":
            val = str(raw_time).zfill(4)
            if len(val) == 4:
                return f"{val[:2]}:{val[2:]}"
            return val
        return "00:00"
