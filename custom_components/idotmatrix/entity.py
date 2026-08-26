"""Shared base entity for the iDotMatrix device."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity

from .client import IdotMatrixClient, IdotMatrixError
from .const import DOMAIN


class IdotMatrixEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        client: IdotMatrixClient,
        availability,
        device_name: str,
        key: str,
    ) -> None:
        self._client = client
        self._availability = availability
        self._attr_unique_id = f"{client.address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.address)},
            connections={(dr.CONNECTION_BLUETOOTH, client.address)},
            name=device_name,
            manufacturer="iDotMatrix",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._availability.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._availability.available

    async def _run(self, coro) -> None:
        """Execute a client command, translating errors for HA."""
        try:
            await coro
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err
