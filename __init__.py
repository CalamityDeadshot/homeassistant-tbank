from dataclasses import dataclass
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import Client
from .const import KEY_CODE, KEY_SELENIUM_URL, KEY_USER_PREFIX, logger
from .coordinator import TBankUpdateCoordinator

DOMAIN = "tbank"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required("selenium_url"): str,
        vol.Required("code"): int
    })
}, extra=2)

PLATFORMS = [Platform.SENSOR]

@dataclass
class RuntimeData:
    client: Client
    user_prefix: str
    coordinator: TBankUpdateCoordinator

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry[RuntimeData]):
    logger.info(config)
    selenium_url = config.data[KEY_SELENIUM_URL]
    quick_code = config.data[KEY_CODE]
    user_prefix = config.data[KEY_USER_PREFIX]
    logger.info(f"Selenium url: {selenium_url}, code: {quick_code}, user prefix: {user_prefix}")
    client = Client(selenium_url, quick_code, user_prefix)
    coordinator = TBankUpdateCoordinator(hass, config, client, user_prefix)

    await coordinator.async_config_entry_first_refresh()
    config.runtime_data = RuntimeData(
        client=client,
        user_prefix=user_prefix,
        coordinator=coordinator
    )

    await hass.config_entries.async_forward_entry_setups(config, [Platform.SENSOR])
    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry.

    This is called when you remove your integration or shutdown HA.
    If you have created any custom services, they need to be removed here too.
    """

    # Unload platforms and return result
    return await hass.config_entries.async_unload_platforms(config_entry, [Platform.SENSOR])
