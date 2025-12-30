import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .client import Client
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

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> Client:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = Client(data[KEY_SELENIUM_URL], "0000", data[KEY_USER_PREFIX])
    success = await hass.async_add_executor_job(client.testConnection)
    if (not success):
        raise SeleniumUnavailable
    return client

class TBankConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    VERSION = 1
    _input_data: dict[str, Any]
    _title: str

    def __init__(self) -> None:
        super().__init__()
        self._client: Client | None = None
        self._entry_id: str | None = None

    async def async_step_user(self, user_input: dict[str, Any]):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._client = await validate_input(self.hass, user_input)
            except SeleniumUnavailable:
                errors["base"] = "selenium_unavailable"
            except Exception as ex:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                user_prefix = user_input[KEY_USER_PREFIX]
                self._entry_id = "root" if user_prefix == "" else user_prefix
                self._input_data = user_input
                return await self.async_step_authentication()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            last_step=False,  # Adding last_step True/False decides whether form shows Next or Submit buttons
        )

    async def async_step_authentication(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        _LOGGER.info(f"Moving to auth step. User data: {user_input}")
        errors = {}

        if (user_input is not None and self._client is not None):
            has_access = await self.hass.async_add_executor_job(self._client.test_access)
            if not has_access:
                raise AuthFailed
            await self.async_set_unique_id(self._entry_id)
            self._abort_if_unique_id_configured()
            self._input_data.update(user_input)
            return self.async_create_entry(
                title=f"{self._entry_id}",
                data=self._input_data
            )

        if (self._client is not None):
            await self.hass.async_add_executor_job(self._client.enter_auth_flow)

        return self.async_show_form(
            step_id="authentication",
            data_schema=STEP_CODE_DATA_SCHEMA,
            errors=errors,
            last_step=True,  # Adding last_step True/False decides whether form shows Next or Submit buttons
        )

class SeleniumUnavailable(HomeAssistantError):
    """Error to indicate Selenium Grid is unavailable"""

class AuthFailed(HomeAssistantError):
    """Error to indicate that T-Bank auth step failed"""
