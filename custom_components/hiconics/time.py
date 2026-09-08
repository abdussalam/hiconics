"""Time platform for Hiconics TOU slots."""

import logging
from datetime import time
from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
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
        super().__init__(coordinator)
        self.entry = entry
        self._slot = slot
        self._is_start = is_start

        base_reg = 40 + ((slot - 1) * 6)
        self._reg = f"C{base_reg}" if is_start else f"C{base_reg + 1}"

        time_type = "Start" if is_start else "End"
        self._attr_name = f"Slot {slot} {time_type}"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_tou_time_{slot}_{time_type.lower()}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self) -> time | None:
        """Return the current time from the coordinator as a datetime.time object."""
        extra_data = getattr(self.coordinator, "extra_data", {})
        raw_time = extra_data.get(self._reg)
        if raw_time and str(raw_time) != "None":
            val = str(raw_time).zfill(4)
            if len(val) == 4:
                try:
                    return time(hour=int(val[:2]), minute=int(val[2:]))
                except ValueError:
                    pass
        return time(hour=0, minute=0)

    async def async_set_value(self, value: time) -> None:
        """Handle the time being changed in the UI."""
        extra = getattr(self.coordinator, "extra_data", {})
        base_reg = 40 + ((self._slot - 1) * 6)

        def get_val(offset, default): 
            return extra.get(f"C{base_reg + offset}", default)

        # Format the chosen time back to Solarman's 'HHMM' string
        time_str = f"{value.hour:02d}{value.minute:02d}"
        
        start = time_str if self._is_start else str(get_val(0, "0000")).zfill(4)
        end = time_str if not self._is_start else str(get_val(1, "0000")).zfill(4)
        
        payload = {
            "slot": self._slot,
            "start_time": start,
            "end_time": end,
            "mode": int(get_val(2, 0)),
            "max_amps": float(get_val(3, 25)),
            "max_soc": float(get_val(4, 100)),
            "min_soc": float(get_val(5, 18))
        }

        # Fire off the update to the inverter
        await self.hass.services.async_call(DOMAIN, "set_tou_slot", payload)
        
        # Update the UI immediately without waiting for next poll
        self.coordinator.extra_data[self._reg] = time_str
        self.async_write_ha_state()
