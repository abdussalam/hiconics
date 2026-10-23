"""The Hiconics Solarman Component."""

import asyncio
import json
import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr

from .api import SolarmanAPIClient
from .coordinator import HiconicsDataCoordinator
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "select", "switch", "button", "time"]

SERVICE_SET_TOU_SLOT = "set_tou_slot"
SERVICE_SET_INVERTER_MODE = "set_inverter_mode"
SERVICE_READ_SETTINGS = "read_settings"
SERVICE_SEND_COMMAND = "send_command"

SET_TOU_SLOT_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): cv.string,
    vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
    vol.Optional("start_time"): cv.string,
    vol.Optional("end_time"): cv.string,
    vol.Optional("mode"): vol.Coerce(str),
    vol.Optional("max_amps"): vol.Coerce(str),
    vol.Optional("max_soc"): vol.Coerce(str),
    vol.Optional("min_soc"): vol.Coerce(str),
})

SET_INVERTER_MODE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): cv.string,
    vol.Required("mode"): cv.string,
})

READ_SETTINGS_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): cv.string,
    vol.Optional("type", default="tou"): vol.In(["tou", "mode", "battery"]),
})

SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): cv.string,
    vol.Required("code"): cv.string,
    vol.Optional("operation_type", default=5): vol.Coerce(int),
    vol.Optional("input_param", default={}): dict,
    vol.Optional("timeout", default=180): vol.Coerce(int),
})


def _get_entry_data(hass: HomeAssistant, call: ServiceCall):
    entry_id = call.data.get("entry_id")
    entries = hass.data.get(DOMAIN, {})
    if entry_id:
        entry_data = entries.get(entry_id)
    elif len(entries) == 1:
        entry_data = next(iter(entries.values()))
    else:
        raise HomeAssistantError("Multiple entries found. Please specify entry_id.")
    if not entry_data:
        raise HomeAssistantError("Hiconics integration entry not loaded.")
    return entry_data


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register services once globally."""
    hass.data.setdefault(DOMAIN, {})

    async def _fetch_and_update_registers(api, coordinator, setting_type: str = "tou"):
        code_map = {"mode": "r_A1", "battery": "r_A6", "tou": "r_A8"}
        code = code_map.get(setting_type, "r_A8")
        param_key = "C1" if setting_type == "mode" else "C32"

        _LOGGER.info("Fetching '%s' registers from inverter (code %s)...", setting_type, code)
        try:
            res = await api.async_send_command(code=code, operation_type=4, input_param={param_key: {"v": "1"}})
            analysis_raw = res.get("analysisResult")

            if analysis_raw:
                parsed = json.loads(analysis_raw) if isinstance(analysis_raw, str) else analysis_raw
                if isinstance(parsed, dict) and parsed:
                    flat_data = {
                        k: str(v["v"]) if isinstance(v, dict) and "v" in v else str(v)
                        for k, v in parsed.items()
                    }
                    coordinator.update_extra_data(flat_data, is_tou=(setting_type == "tou"))
                    return True
        except Exception as err:
            _LOGGER.error("Failed to parse read_settings response for %s: %s", setting_type, err)
        return False

    async def handle_set_tou_slot(call: ServiceCall):
        entry_data = _get_entry_data(hass, call)
        api, coordinator = entry_data["api"], entry_data["coordinator"]

        slot = call.data["slot"]
        base_reg = 40 + ((slot - 1) * 6)

        def get_clean_reg(reg_offset: int) -> str:
            key = f"C{base_reg + reg_offset}"
            val = coordinator.extra_data.get(key, "")
            val_str = str(val).replace(":", "").strip()
            if "-" in val_str:
                val_str = val_str.split("-")[0].strip()
            if val_str.replace(".", "", 1).isdigit():
                val_str = str(int(float(val_str)))
            return val_str

        start_time = str(call.data.get("start_time", get_clean_reg(0))).replace(":", "").strip().zfill(4)
        end_time = str(call.data.get("end_time", get_clean_reg(1))).replace(":", "").strip().zfill(4)

        raw_mode = str(call.data.get("mode", get_clean_reg(2)))
        mode = raw_mode.split("-")[0].strip() if "-" in raw_mode else str(int(float(raw_mode)))

        max_amps = str(int(float(call.data.get("max_amps", get_clean_reg(3)))))
        max_soc = str(int(float(call.data.get("max_soc", get_clean_reg(4)))))
        min_soc = str(int(float(call.data.get("min_soc", get_clean_reg(5)))))

        params = {
            f"C{base_reg}": {"v": start_time},
            f"C{base_reg+1}": {"v": end_time},
            f"C{base_reg+2}": {"v": mode},
            f"C{base_reg+3}": {"v": max_amps},
            f"C{base_reg+4}": {"v": max_soc},
            f"C{base_reg+5}": {"v": min_soc},
        }

        _LOGGER.debug("Sending TOU Slot %s s_A8 payload: %s", slot, params)
        await api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        coordinator.update_extra_data({k: v["v"] for k, v in params.items()}, is_tou=True)

        await asyncio.sleep(15)
        await _fetch_and_update_registers(api, coordinator, "tou")

    async def handle_set_inverter_mode(call: ServiceCall):
        entry_data = _get_entry_data(hass, call)
        api, coordinator = entry_data["api"], entry_data["coordinator"]
        raw_mode = str(call.data["mode"])
        mode = raw_mode.split("-")[0].strip() if "-" in raw_mode else str(int(float(raw_mode)))
        await api.async_send_command(code="s_A1", operation_type=5, input_param={"C1": {"v": mode}})
        await asyncio.sleep(15)
        await _fetch_and_update_registers(api, coordinator, "mode")

    async def handle_read_settings(call: ServiceCall):
        entry_data = _get_entry_data(hass, call)
        await _fetch_and_update_registers(entry_data["api"], entry_data["coordinator"], call.data["type"])

    async def handle_send_command(call: ServiceCall):
        entry_data = _get_entry_data(hass, call)
        await entry_data["api"].async_send_command(
            code=call.data["code"],
            operation_type=call.data["operation_type"],
            input_param=call.data["input_param"],
            timeout=call.data["timeout"],
        )

    hass.services.async_register(DOMAIN, SERVICE_SET_TOU_SLOT, handle_set_tou_slot, schema=SET_TOU_SLOT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_INVERTER_MODE, handle_set_inverter_mode, schema=SET_INVERTER_MODE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_READ_SETTINGS, handle_read_settings, schema=READ_SETTINGS_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SEND_COMMAND, handle_send_command, schema=SEND_COMMAND_SCHEMA)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hiconics from a config entry."""
    api_config = dict(entry.data)
    api_config.update(entry.options)

    session = async_get_clientsession(hass)
    api = SolarmanAPIClient(session, api_config)

    scan_interval = api_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = HiconicsDataCoordinator(hass, api, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
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

    async def _async_startup_fetch():
        """Fetch all configurations from hardware upon integration boot."""
        _LOGGER.info("Starting background fetch of inverter settings...")
        await asyncio.sleep(5)
        for setting_type in ("mode", "battery", "tou"):
            code_map = {"mode": "r_A1", "battery": "r_A6", "tou": "r_A8"}
            param_key = "C1" if setting_type == "mode" else "C32"
            try:
                res = await api.async_send_command(code=code_map[setting_type], operation_type=4, input_param={param_key: {"v": "1"}})
                raw = res.get("analysisResult") if res else None
                if raw:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, dict):
                        coordinator.update_extra_data(
                            {
                                k: str(v["v"]) if isinstance(v, dict) and "v" in v else str(v)
                                for k, v in parsed.items()
                            },
                            is_tou=(setting_type == "tou"),
                        )
            except Exception as err:
                _LOGGER.error("Startup fetch error for %s: %s", setting_type, err)
            await asyncio.sleep(3)

    entry.async_create_background_task(hass, _async_startup_fetch(), name=f"{DOMAIN}_startup_{entry.entry_id}")

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            for service in (SERVICE_SET_TOU_SLOT, SERVICE_SET_INVERTER_MODE, SERVICE_READ_SETTINGS, SERVICE_SEND_COMMAND):
                hass.services.async_remove(DOMAIN, service)
    return unload_ok
