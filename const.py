import logging

import voluptuous as vol

DOMAIN = "tbank"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required("selenium_url"): str,
        vol.Required("code"): int
    })
}, extra=2)

KEY_SELENIUM_URL: str = "selenium_url"
KEY_USER_PREFIX: str = "user_prefix"
KEY_CODE: str = "code"

logger = logging.getLogger(DOMAIN)
