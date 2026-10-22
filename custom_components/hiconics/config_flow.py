"""Config flow for Hiconics integration."""

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolarmanAPIClient, HiconicsAuthError, HiconicsConnectionError
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
    CONF_API_DOMAIN,
    CONF_PRODUCT_CODE,
    CONF_CODE_GROUP,
    DEFAULT_API_DOMAIN,
    DEFAULT_PRODUCT_CODE,
    DEFAULT_CODE_GROUP,
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
        vol.Optional(CONF_API_DOMAIN, default=DEFAULT_API_DOMAIN): str,
        vol.Optional(CONF_PRODUCT_CODE, default=DEFAULT_PRODUCT_CODE): str,
        vol.Optional(CONF_CODE_GROUP, default=DEFAULT_CODE_GROUP): str,
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

            session = async_get_clientsession(self.hass)
            api = SolarmanAPIClient(session, user_input)

            try:
                await api.async_get_token()
                await api.async_get_device_data()
            except HiconicsAuthError:
                errors["base"] = "invalid_auth"
            except (HiconicsConnectionError, Exception):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Hiconics Inverter ({user_input[CONF_DEVICE_SN]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Handle re-authentication trigger."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Confirm re-authentication with new credentials."""
        errors = {}
        reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None and reauth_entry is not None:
            updated_data = {**reauth_entry.data, **user_input}
            session = async_get_clientsession(self.hass)
            api = SolarmanAPIClient(session, updated_data)
            try:
                await api.async_get_token()
                await api.async_get_device_data()
            except HiconicsAuthError:
                errors["base"] = "invalid_auth"
            except (HiconicsConnectionError, Exception):
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(reauth_entry, data=updated_data)
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HiconicsOptionsFlowHandler()


class HiconicsOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Hiconics."""

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
                vol.Optional(CONF_API_DOMAIN, default=current.get(CONF_API_DOMAIN, DEFAULT_API_DOMAIN)): str,
                vol.Optional(CONF_PRODUCT_CODE, default=current.get(CONF_PRODUCT_CODE, DEFAULT_PRODUCT_CODE)): str,
                vol.Optional(CONF_CODE_GROUP, default=current.get(CONF_CODE_GROUP, DEFAULT_CODE_GROUP)): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
