"""Switch platform for Hiconics System Controls."""

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics switch entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    switches = [
        HiconicsControlSwitch(coordinator, api, entry, "C32", "Battery Sleep Mode", "s_A6"),
        HiconicsControlSwitch(coordinator, api, entry, "C216", "Grid Charging", "s_A6"),
    ]
    async_add_entities(switches)


class HiconicsControlSwitch(CoordinatorEntity, SwitchEntity):
    """Interactive switch control for Hiconics system toggles."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, entry, reg_key: str, name: str, command_code: str):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._reg_key = reg_key
        self._attr_name = name
        self._command_code = command_code
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sw_{reg_key}"

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
    def is_on(self) -> bool:
        val = str(self.coordinator.extra_data.get(self._reg_key, "0"))
        return val == "1"

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state("1")

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state("0")

    async def _set_state(self, state_val: str) -> None:
        params = {self._reg_key: {"v": state_val}}
        _LOGGER.info("Updating switch %s (%s) to %s...", self._attr_name, self._reg_key, state_val)
        await self.api.async_send_command(code=self._command_code, operation_type=5, input_param=params)
        self.coordinator.update_extra_data({self._reg_key: state_val})
