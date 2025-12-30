from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import Client, SessionError

_LOGGER = logging.getLogger(__name__)
class TBankUpdateCoordinator(DataUpdateCoordinator):

    data: dict[str, Any]
    entities_lookup: dict[str, dict[str, Any]]

    def __init__(self, ha: HomeAssistant, config: ConfigEntry, client: Client, user_prefix: str):
        super().__init__(
            ha,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="T-Bank money sensor",
            config_entry=config,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(hours=3),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True
        )
        _LOGGER.info(f"Initializing coordinator with config: {config}")
        self.client: Client = client
        self.user_prefix: str = user_prefix

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            self.data = await self.hass.async_add_executor_job(self.client.run)
            self.entities_lookup = _construct_lookup(self.data, self.user_prefix)
        except SessionError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            _LOGGER.error(err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        return self.entities_lookup

def _construct_lookup(data: dict, user_prefix: str) -> dict[str, dict[str, Any]]:
    def toSnakeCase(s: str) -> str:
        return ('_').join(s.split())

    def generateTranslation():
        return {1072: 97, 1073: 98, 1074: 118, 1075: 103, 1076: 100, 1077: 101, 1105: 101, 1078: 106, 1079: 122, 1080: 105, 1081: 106, 1082: 107, 1083: 108, 1084: 109, 1085: 110, 1086: 111, 1087: 112, 1088: 114, 1089: 115, 1090: 116, 1091: 117, 1092: 102, 1093: 104, 1094: 122, 1095: 99, 1096: 115, 1097: 115, 1098: 95, 1099: 121, 1100: 95, 1101: 101, 1102: 117, 1103: 97, 1040: 65, 1041: 66, 1042: 86, 1043: 71, 1044: 68, 1045: 69, 1025: 69, 1046: 74, 1047: 90, 1048: 73, 1049: 74, 1050: 75, 1051: 76, 1052: 77, 1053: 78, 1054: 79, 1055: 80, 1056: 82, 1057: 83, 1058: 84, 1059: 85, 1060: 70, 1061: 72, 1062: 90, 1063: 67, 1064: 83, 1065: 83, 1066: 95, 1067: 89, 1068: 95, 1069: 69, 1070: 85, 1071: 65}

    def prefix(entity_id: str) -> str:
        if user_prefix == "" or user_prefix == "root":
            return entity_id
        return f"{user_prefix}_{entity_id}".lower()

    lookup: dict[str, dict[str, Any]] = {}
    tr = generateTranslation()
    bank_accounts = []
    sum = 0

    for bank_account in data['bank']:
        account_name = bank_account["name"]
        snaked = toSnakeCase(account_name).translate(tr)
        # logger.info(f"{account_name} -> {snaked}")
        currency = bank_account["money"]["currency"]
        money = bank_account["money"]["amount"]
        acc_type = bank_account["type"]
        sum += money if acc_type != "Credit" and currency == "RUB" else 0
        attribs = {
            "currency": bank_account["money"]["currency"],
            "type": acc_type,
            "unit_of_measurement": "₽" if currency == "RUB" else "$",
            "friendly_name": account_name
        }
        account_entity_id = f"sensor.{prefix(f"money_bank_{snaked}")})".lower()
        bank_accounts.append(account_entity_id)
        lookup[account_entity_id] = {
            'state': money,
            'attributes': attribs
        }

    lookup[f"sensor.{prefix("money_bank")}"] = {
        'state': sum,
        'attributes': {
            "currency": "RUB",
            "unit_of_measurement": "₽",
            "accounts": data["bank"],
            "children": bank_accounts,
            "friendly_name": "Bank"
        }
    }

    sum = 0
    investment_accounts = []
    for investment_account in data["investments"]:
        account_name = investment_account["name"].replace("Брокерский счет", "Brokerage account")
        snaked = toSnakeCase(account_name).translate(tr)
        currency = investment_account["money"]["currency"]
        money = investment_account["money"]["amount"]
        sum += money
        account_sensor_name = f"sensor.{prefix(f"money_invest_{snaked}")}".lower()
        position_entities = []
        for position in investment_account["money"]["positions"]:
            totalRub = position["money"]["RUB"]["total"]
            ticker_stripped = ''.join(c for c in position["ticker"] if c.isalnum())
            position["friendly_name"] = f"{position["display"]["name"]} ({account_name})"
            position["unit_of_measurement"] = "₽"
            position_entity_id = f"{account_sensor_name}_{ticker_stripped}".lower()
            position_entities.append(position_entity_id)
            lookup[position_entity_id] = {
                'state': totalRub,
                'attributes': position
            }

        attribs = {
            "currency": investment_account["money"]["currency"],
            "unit_of_measurement": "₽" if currency == "RUB" else "$",
            "friendly_name": account_name,
            "positions": investment_account["money"]["positions"],
            "children": position_entities
        }
        investment_accounts.append(account_sensor_name)
        lookup[account_sensor_name] = {
            'state': money,
            'attributes': attribs
        }

    lookup[f"sensor.{prefix("money_invest")}"] = {
        'state': sum,
        'attributes': {
            "currency": "RUB",
            "unit_of_measurement": "₽",
            "accounts": data["investments"],
            "children": investment_accounts,
            "friendly_name": "Invested"
        }
    }
    return lookup
