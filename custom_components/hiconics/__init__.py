"""The Hiconics Solarman Component."""

import json
import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr

from .api import SolarmanAPIClient
from .coordinator import HiconicsDataCoordinator
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hiconics from a config entry."""
    
    # Merge entry.data and entry.options so changes in the UI apply correctly
    api_config = dict(entry.data)
    api_config.update(entry.options)

    session = async_get_clientsession(hass)
    api = SolarmanAPIClient(session, api_config)

    scan_interval = api_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = HiconicsDataCoordinator(hass, api, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_inverter")},
        manufacturer="Hiconics",
        model="HECS2-S6",
        name="Hiconics Inverter",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for configuration option changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Keep your existing service definitions here (set_tou_slot, set_inverter_mode, send_command, read_settings)
    # ... [Insert the existing service registrations from the previous code here] ...

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
