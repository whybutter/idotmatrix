"""Advertisement-based availability tracking.

The panel gives us no pollable state, but it advertises continuously — so
"an adapter/proxy has seen it recently" is the honest availability signal.
HA's bluetooth component already tracks this; we just subscribe.
"""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback


class IdotMatrixAvailability:
    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self._listeners: list[Callable[[], None]] = []
        self._available = bluetooth.async_address_present(
            hass, address, connectable=True
        )
        self._unsubs = [
            bluetooth.async_register_callback(
                hass,
                self._async_advertisement,
                {"address": address, "connectable": True},
                bluetooth.BluetoothScanningMode.PASSIVE,
            ),
            bluetooth.async_track_unavailable(
                hass, self._async_unavailable, address, connectable=True
            ),
        ]

    @property
    def available(self) -> bool:
        return self._available

    @callback
    def _async_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        if not self._available:
            self._available = True
            self._async_notify()

    @callback
    def _async_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        self._available = False
        self._async_notify()

    @callback
    def _async_notify(self) -> None:
        for listener in self._listeners:
            listener()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsub() -> None:
            self._listeners.remove(listener)

        return _unsub

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        self._listeners = []
