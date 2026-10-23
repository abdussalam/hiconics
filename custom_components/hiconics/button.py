"""Button platform for Hiconics integration."""

import logging
import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = [
        HiconicsPullTouButton(coordinator, api, entry),
        HiconicsPullInverterModeButton(coordinator, api, entry),
        HiconicsPullBatteryButton(coordinator, api, entry),
        HiconicsApplyAllTouButton(coordinator, api, entry),
    ]

    async_add_entities(entities)


class HiconicsPullTouButton(CoordinatorEntity, ButtonEntity):
    """Button to pull TOU settings from the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Pull TOU Settings"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_pull_tou"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Read TOU settings from API."""
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"entry_id": self.entry.entry_id, "type": "tou"}
        )


class HiconicsPullInverterModeButton(CoordinatorEntity, ButtonEntity):
    """Button to pull Inverter Mode settings from the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Pull Inverter Mode"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_pull_mode"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Read Inverter Mode settings from API."""
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"entry_id": self.entry.entry_id, "type": "mode"}
        )


class HiconicsPullBatteryButton(CoordinatorEntity, ButtonEntity):
    """Button to pull Battery settings from the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Pull Battery Settings"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_pull_battery"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Read Battery settings from API."""
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"entry_id": self.entry.entry_id, "type": "battery"}
        )


class HiconicsApplyAllTouButton(CoordinatorEntity, ButtonEntity):
    """Button to push all staged TOU slots to the inverter with busy-state disabling."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-upload"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Apply TOU Settings"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._is_busy = False
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_apply_all_tou"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def available(self) -> bool:
        """Return False to grey out/disable the button while an API action is in progress."""
        if self._is_busy:
            return False
        return super().available

    async def async_press(self) -> None:
        """Push all 36 TOU registers in a single batch call while locking the button."""
        self._is_busy = True
        self.async_write_ha_state()

        try:
            params = {}

            for reg in range(40, 76):
                key = f"C{reg}"
                val = self.coordinator.extra_data.get(key)
                
                if val is None or str(val).strip() == "" or str(val).lower() == "none":
                    raise HomeAssistantError(f"Cannot apply settings: Register {key} is empty or unread. Please click 'Pull TOU Settings' first.")

                val_str = str(val).replace(":", "").strip()
                if "-" in val_str:
                    val_str = val_str.split("-")[0].strip()
                if val_str.replace(".", "", 1).isdigit():
                    val_str = str(int(float(val_str)))

                slot_offset = (reg - 40) % 6
                if slot_offset in (0, 1):
                    val_str = val_str.zfill(4)

                params[key] = {"v": val_str}

            _LOGGER.debug("Sending all TOU slots in single s_A8 batch payload: %s", params)
            
            await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
            self.coordinator.update_extra_data({k: v["v"] for k, v in params.items()}, is_tou=True)

        except Exception as err:
            if "OR_THERE_ARE_ORDER_BEING_SENT" in str(err):
                raise HomeAssistantError("Inverter is busy processing another command. Please wait 10 seconds and try again.")
            raise
        finally:
            # Always re-enable the button once finished or failed
            self._is_busy = False
            self.async_write_ha_state()
