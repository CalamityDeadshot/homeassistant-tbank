import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RuntimeData
from .const import DOMAIN, logger
from .coordinator import TBankUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry[RuntimeData],
    async_add_entities: AddEntitiesCallback
):
    logger.info(f"async_setup_entry for sensors. Config: {config_entry}")
    coordinator = config_entry.runtime_data.coordinator

    async_add_entities(
        [MoneySensor(coordinator, entity_id, str(config_entry.unique_id)) for entity_id in coordinator.entities_lookup]
    )

class MoneySensor(CoordinatorEntity[TBankUpdateCoordinator], SensorEntity):
    """Implementation of a sensor."""

    data: dict[str, Any]

    def __init__(self, coordinator: TBankUpdateCoordinator, entity_id: str, entry_id: str) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.entity_id = entity_id
        self.data = coordinator.entities_lookup[entity_id]
        self.entry_id = entry_id

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        self.data = self.coordinator.entities_lookup[self.entity_id]
        self.async_write_ha_state()

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-device-classes
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Identifiers are what group entities into the same device.
        # If your device is created elsewhere, you can just specify the indentifiers parameter.
        # If your device connects via another device, add via_device parameter with the indentifiers of that device.
        name = "T-Bank Account" if self.entry_id in {"", "root"} else f"T-Bank Account ({self.entry_id})"
        return DeviceInfo(
            name=name,
            manufacturer="T-Bank",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    self.entry_id,
                )
            },
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.data['attributes']['friendly_name']

    @property
    def native_value(self) -> int | float:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.
        return float(self.data['state'])

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of temperature."""
        return self.data['attributes']['unit_of_measurement']

    @property
    def state_class(self) -> str | None:
        """Return state class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
        return SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.entry_id}-{self.entity_id}"

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        # Add any additional attributes you want on your sensor.
        return self.data['attributes']

    @property
    def suggested_display_precision(self) -> int | None:
        """Return 2 for money."""
        return 2
