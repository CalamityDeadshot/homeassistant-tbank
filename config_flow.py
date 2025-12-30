import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .client import AuthFailed, Client, SeleniumUnavailable
from .const import DOMAIN, KEY_CODE, KEY_SELENIUM_URL, KEY_USER_PREFIX

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(KEY_SELENIUM_URL, description={"suggested_value": "http://homeassistant.local:4444"}): str,
        vol.Optional(KEY_USER_PREFIX, default="root"): str
    }
)

STEP_CODE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(KEY_CODE, description={"suggested_value": "1111"}): vol.All(
            vol.Length(4, 4),
            vol.Coerce(str)
        )
    }
)

def step_user_schema(existing_input: MappingProxyType[str, Any] | dict[str, Any] | None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(KEY_SELENIUM_URL, description={"suggested_value": f"{existing_input[KEY_SELENIUM_URL] if existing_input else "http://homeassistant.local:4444"}"}): str,
            vol.Optional(KEY_USER_PREFIX, default=f"{existing_input[KEY_USER_PREFIX] if existing_input else "root"}"): str
        }
    )

def step_code_schema(existing_input: MappingProxyType[str, Any] | dict[str, Any] | None) -> vol.Schema:
    _LOGGER.info(f"Generating code step schema. Existing input: {existing_input}. Code: {existing_input[KEY_CODE] if existing_input else "1111"}")
    return vol.Schema(
        {
            vol.Required(KEY_CODE, description={"suggested_value": f"{existing_input[KEY_CODE] if existing_input else "1111"}"}): vol.All(
                vol.Length(4, 4),
                vol.Coerce(str)
            )
        }
    )

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> Client:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = Client(data[KEY_SELENIUM_URL], "0000", data[KEY_USER_PREFIX])
    await hass.async_add_executor_job(client.testConnection)
    return client

class TBankConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow for T-Bank web client."""
    VERSION = 1
    _input_data: dict[str, Any]
    _title: str

    def __init__(self) -> None:
        super().__init__()
        self._client: Client | None = None
        self._entry_id: str | None = None
        self.reconfig_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._client = await validate_input(self.hass, user_input)
            except SeleniumUnavailable:
                errors["base"] = "selenium_unavailable"
            except Exception as ex:
                _LOGGER.exception(f"Unexpected exception: {ex}")
                errors["base"] = "unknown"

            if "base" not in errors:
                user_prefix = user_input[KEY_USER_PREFIX]
                self._entry_id = "root" if user_prefix == "" else user_prefix
                self._input_data = user_input
                _LOGGER.info(f"User step -> Auth step with reconfig_entry={self.reconfig_entry}")
                return await self.async_step_authentication()

        _LOGGER.info(f"Launching initial form. Errors: {errors}")
        return self.async_show_form(
            step_id="user",
            data_schema=step_user_schema(self.reconfig_entry.data if self.reconfig_entry else user_input),
            errors=errors,
            last_step=False,  # Adding last_step True/False decides whether form shows Next or Submit buttons
        )

    async def async_step_authentication(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        _LOGGER.info(f"Moving to auth step. User data: {user_input}, reconfig data: {self.reconfig_entry.data if self.reconfig_entry else None} ({self.reconfig_entry})")
        errors = {}

        if (user_input is not None and self._client is not None):
            try:
                await self.hass.async_add_executor_job(self._client.test_access)
            except AuthFailed:
                errors['base'] = "auth_failed"
            except SeleniumUnavailable:
                errors["base"] = "selenium_unavailable"
            except Exception:
                errors["base"] = "unknown"

            if "base" not in errors:
                self._input_data.update(user_input)
                if (self.reconfig_entry):
                    return self.async_update_reload_and_abort(
                        self.reconfig_entry,
                        unique_id=self.reconfig_entry.unique_id,
                        data={**self.reconfig_entry.data, ** self._input_data},
                        reason="reconfigure_successful"
                    )
                await self.async_set_unique_id(self._entry_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{self._entry_id}",
                    data=self._input_data
                )

        if (self._client is not None and "base" not in errors):
            await self.hass.async_add_executor_job(self._client.enter_auth_flow)

        return self.async_show_form(
            step_id="authentication",
            data_schema=step_code_schema(self.reconfig_entry.data if self.reconfig_entry else user_input),
            errors=errors,
            last_step=True,  # Adding last_step True/False decides whether form shows Next or Submit buttons
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        config_entry: config_entries.ConfigEntry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        _LOGGER.info(f"Reconfiguration started. Existing data: {config_entry.data}")
        self.reconfig_entry = config_entry
        return await self.async_step_user(user_input)
