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
    
    # Merge entry.data and entry.options so UI configuration changes apply
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

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # 1. TOU Control Action
    async def handle_set_tou_slot(call: ServiceCall):
        slot = call.data.get("slot", 1)
        start_time = call.data.get("start_time", "0000").replace(":", "")
        end_time = call.data.get("end_time", "0000").replace(":", "")
        mode = str(call.data.get("mode", 0))
        max_amps = str(call.data.get("max_amps", 25))
        max_soc = str(call.data.get("max_soc", 100))
        min_soc = str(call.data.get("min_soc", 18))

        base_reg = 40 + ((slot - 1) * 6)
        params = {
            f"C{base_reg}": {"v": start_time},
            f"C{base_reg+1}": {"v": end_time},
            f"C{base_reg+2}": {"v": mode},
            f"C{base_reg+3}": {"v": max_amps},
            f"C{base_reg+4}": {"v": max_soc},
            f"C{base_reg+5}": {"v": min_soc},
        }

        await api.async_send_command(code="s_A8", operation_type=5, input_param=params)

        flat_params = {k: v["v"] for k, v in params.items()}
        coordinator.update_extra_data(flat_params)

    # 2. Inverter Mode Control Action
    async def handle_set_inverter_mode(call: ServiceCall):
        mode = str(call.data.get("mode", "1"))
        params = {"C1": {"v": mode}}
        await api.async_send_command(code="s_A1", operation_type=5, input_param=params)

    # 3. Read Settings Action
    async def handle_read_settings(call: ServiceCall):
        setting_type = call.data.get("type", "tou")
        code_map = {"mode": "r_A1", "battery": "r_A6", "tou": "r_A8"}
        code = code_map.get(setting_type, "r_A8")
        param_key = "C1" if setting_type == "mode" else "C32"

        res = await api.async_send_command(code=code, operation_type=4, input_param={param_key: {"v": "1"}})

        analysis_raw = res.get("analysisResult")
        if analysis_raw:
            try:
                parsed = json.loads(analysis_raw) if isinstance(analysis_raw, str) else analysis_raw
                if isinstance(parsed, dict):
                    coordinator.update_extra_data(parsed)
                    _LOGGER.info("Successfully fetched and updated %s register sensors.", setting_type)
            except Exception as err:
                _LOGGER.error("Failed to parse read_settings response: %s", err)

    # 4. Raw API Send Command Action
    async def handle_send_command(call: ServiceCall):
        code = call.data.get("code")
        op_type = int(call.data.get("operation_type", 5))
        input_param = call.data.get("input_param", {})
        timeout = int(call.data.get("timeout", 180))

        await api.async_send_command(code=code, operation_type=op_type, input_param=input_param, timeout=timeout)

    hass.services.async_register(DOMAIN, "set_tou_slot", handle_set_tou_slot)
    hass.services.async_register(DOMAIN, "set_inverter_mode", handle_set_inverter_mode)
    hass.services.async_register(DOMAIN, "read_settings", handle_read_settings)
    hass.services.async_register(DOMAIN, "send_command", handle_send_command)

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
