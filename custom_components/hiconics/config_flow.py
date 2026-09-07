"""Config flow for Hiconics integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolarmanAPIClient
from .const import (
    DOMAIN,
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_SN,
    CONF_DEVICE_ID,
    CONF_PRODUCT,
    CONF_CODE_GROUP,
    CONF_SCAN_INTERVAL,
    DEFAULT_APP_ID,
    DEFAULT_PRODUCT,
    DEFAULT_CODE_GROUP,
    DEFAULT_SCAN_INTERVAL,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_APP_SECRET): str,
        vol.Required(CONF_DEVICE_SN): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_APP_ID, default=DEFAULT_APP_ID): str,
        vol.Optional(CONF_PRODUCT, default=DEFAULT_PRODUCT): str,
        vol.Optional(CONF_CODE_GROUP, default=DEFAULT_CODE_GROUP): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


class HiconicsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hiconics."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = SolarmanAPIClient(session, user_input)
            try:
                await client.async_get_token()
                await self.async_set_unique_id(user_input[CONF_DEVICE_SN])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Hiconics ({user_input[CONF_DEVICE_SN]})",
                    data=user_input,
                )
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HiconicsOptionsFlowHandler(config_entry)


class HiconicsOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Hiconics options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Pull existing config or fallback to original setup data
        schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=self.config_entry.options.get(CONF_USERNAME, self.config_entry.data.get(CONF_USERNAME))): str,
            vol.Required(CONF_PASSWORD, default=self.config_entry.options.get(CONF_PASSWORD, self.config_entry.data.get(CONF_PASSWORD))): str,
            vol.Required(CONF_APP_SECRET, default=self.config_entry.options.get(CONF_APP_SECRET, self.config_entry.data.get(CONF_APP_SECRET))): str,
            vol.Required(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))): int,
        })
        
        return self.async_show_form(step_id="init", data_schema=schema)
