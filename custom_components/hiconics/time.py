"""Time platform for Hiconics TOU slots."""

import logging
from datetime import time
from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics time entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for slot in range(1, 7):
        entities.append(HiconicsTOUTime(coordinator, entry, slot, is_start=True))
        entities.append(HiconicsTOUTime(coordinator, entry, slot, is_start=False))

    async_add_entities(entities)


class HiconicsTOUTime(CoordinatorEntity, TimeEntity):
    """Native time picker for TOU Start and End Times."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-edit-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, slot: int, is_start: bool):
        """Initialize TOU time entity."""
        super().__init__(coordinator)
        self.entry = entry
        self._slot = slot
        self._is_start = is_start

        base_reg = 40 + ((slot - 1) * 6)
        self._reg = f"C{base_reg}" if is_start else f"C{base_reg + 1}"

        time_type = "Start" if is_start else "End"
        time_label = "A. Start Time" if is_start else "B. End Time"

        self._attr_name = f"Slot {slot} - {time_label}"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_tou_time_{slot}_{time_type.lower()}"

    @property
    def device_info(self):
        """Return inverter device info."""
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self) -> time | None:
        """Return current staged/read time as a datetime.time object."""
        extra_data = getattr(self.coordinator, "extra_data", {})
        raw_time = extra_data.get(self._reg)
        if raw_time is None or str(raw_time) == "None":
            return None
        val = str(raw_time).replace(":", "").strip().zfill(4)
        if len(val) == 4 and val.isdigit():
            try:
                return time(hour=int(val[:2]), minute=int(val[2:]))
            except ValueError:
                return None
        return None

    async def async_set_value(self, value: time) -> None:
        """Stage the time locally without dispatching an API call."""
        base_reg = 40 + ((self._slot - 1) * 6)
        required_keys = [f"C{base_reg + i}" for i in range(6)]

        if not all(k in self.coordinator.extra_data for k in required_keys):
            raise HomeAssistantError("Cannot stage value: TOU register block has not been read from inverter yet.")

        time_str = f"{value.hour:02d}{value.minute:02d}"

        # Stage change in coordinator extra_data locally
        self.coordinator.extra_data[self._reg] = time_str
        self.async_write_ha_state()
