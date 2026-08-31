"""Config flow for iDotMatrix, driven by HA's Bluetooth discovery."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_scanner_devices_by_address,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_GAMMA,
    CONF_PREFERRED_PROXY,
    DEFAULT_GAMMA,
    DOMAIN,
    LOCAL_NAME_PREFIX,
    MAX_GAMMA,
    MIN_GAMMA,
    PROXY_AUTO,
)


class IdotMatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery + manual setup of an iDotMatrix panel."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return IdotMatrixOptionsFlow()

    def __init__(self) -> None:
        self._discovered_address: str | None = None
        self._discovered_name: str | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> Any:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered_address = discovery_info.address
        self._discovered_name = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> Any:
        assert self._discovered_address is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name or self._discovered_address,
                data={CONF_ADDRESS: self._discovered_address},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._discovered_name or ""},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices.get(address, address),
                data={CONF_ADDRESS: address},
            )

        current_addresses = self._async_current_ids()
        self._discovered_devices = {
            info.address: info.name or info.address
            for info in async_discovered_service_info(self.hass)
            if info.address not in current_addresses
            and (info.name or "").startswith(LOCAL_NAME_PREFIX)
        }

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )


class IdotMatrixOptionsFlow(OptionsFlow):
    """Per-panel options: which BLE proxy to use, and the display gamma.

    HA normally picks the proxy with the strongest signal, but the strongest
    one can be unreliable. This lists the proxies currently seeing the panel so
    a specific (more stable) one can be pinned.

    Gamma linearises sRGB source images for the panel's ~linear PWM; 2.2 is the
    correct sRGB value and the measured best match. Lower it toward 1.0 for the
    old (brighter, washed-out) look, or raise it for richer, darker colour.
    """

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        address = self.config_entry.data[CONF_ADDRESS]
        options: dict[str, str] = {PROXY_AUTO: "Auto (best signal)"}
        for dev in async_scanner_devices_by_address(self.hass, address, connectable=True):
            rssi = getattr(dev.advertisement, "rssi", None)
            label = dev.scanner.name or dev.scanner.source
            options[dev.scanner.source] = (
                f"{label} (RSSI {rssi})" if rssi is not None else label
            )

        current = self.config_entry.options.get(CONF_PREFERRED_PROXY, PROXY_AUTO)
        if current not in options:
            options[current] = current

        gamma = self.config_entry.options.get(CONF_GAMMA, DEFAULT_GAMMA)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PREFERRED_PROXY, default=current): vol.In(options),
                    vol.Required(CONF_GAMMA, default=gamma): vol.All(
                        vol.Coerce(float), vol.Range(min=MIN_GAMMA, max=MAX_GAMMA)
                    ),
                }
            ),
        )
