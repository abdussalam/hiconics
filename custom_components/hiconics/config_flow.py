"""Config flow for Hiconics integration."""

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_DEVICE_SN,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_APP_ID): str,
        vol.Required(CONF_APP_SECRET): str,
        vol.Required(CONF_DEVICE_SN): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


class HiconicsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hiconics."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_SN])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Hiconics Inverter ({user_input[CONF_DEVICE_SN]})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HiconicsOptionsFlowHandler(config_entry)


class HiconicsOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Hiconics."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}

        options_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=current.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=current.get(CONF_PASSWORD, "")): str,
                vol.Required(CONF_APP_ID, default=current.get(CONF_APP_ID, "")): str,
                vol.Required(CONF_APP_SECRET, default=current.get(CONF_APP_SECRET, "")): str,
                vol.Required(CONF_DEVICE_SN, default=current.get(CONF_DEVICE_SN, "")): str,
                vol.Required(CONF_DEVICE_ID, default=current.get(CONF_DEVICE_ID, "")): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
