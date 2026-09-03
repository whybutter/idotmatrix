"""Real-time audio spectrum → panel bars.

An external analyzer (e.g. a loopback-capture script on the PC playing the
music) POSTs 8-band levels to this integration's webhook, and each POST is
streamed to the panel as one spectrum frame — the on-device bar visualizer the
official app uses for its phone-audio mode. HA exposes no raw audio itself, so
the analyzer lives wherever the audio actually plays; this is just the fast,
BLE-side sink.

Webhook body (JSON): {"levels": [b0..b7]} where each b is either 0..1 (a
normalized magnitude) or 0..31 (a raw bar height). 8 bands; extra are ignored,
missing are zero-filled. Post at ~12-20 fps.

Design:
- One in-flight write at a time; if a POST arrives while the previous frame is
  still being written, it is dropped (real-time — a stale bar height is worse
  than a skipped one).
- After IDLE_REVERT_SECONDS with no frames the panel returns to its stored
  album, so the visualizer clears itself when the music stops without the
  analyzer having to send a "stop".
"""
from __future__ import annotations

import logging

from homeassistant.components import webhook
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from . import protocol
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Return the panel to its album this long after the last spectrum frame.
IDLE_REVERT_SECONDS = 3.0


class SpectrumBridge:
    """Webhook sink that turns posted band levels into live panel bars."""

    def __init__(self, hass: HomeAssistant, data) -> None:
        self._hass = hass
        self._data = data
        addr = data.client.address.replace(":", "").lower()[-6:]
        self.webhook_id = f"idotmatrix_spectrum_{addr}"
        self._busy = False
        self._cancel_idle = None
        self._active = False

    @callback
    def start(self) -> None:
        webhook.async_register(
            self._hass, DOMAIN, "iDotMatrix spectrum", self.webhook_id, self._handle
        )
        _LOGGER.info(
            "iDotMatrix spectrum webhook ready: %s",
            webhook.async_generate_url(self._hass, self.webhook_id),
        )

    @callback
    def stop(self) -> None:
        webhook.async_unregister(self._hass, self.webhook_id)
        if self._cancel_idle is not None:
            self._cancel_idle()
            self._cancel_idle = None

    @property
    def url(self) -> str:
        return webhook.async_generate_url(self._hass, self.webhook_id)

    async def _handle(self, hass, webhook_id, request):
        try:
            payload = await request.json()
        except ValueError:
            return None
        levels = payload.get("levels")
        if not isinstance(levels, list):
            return None

        bands = []
        for v in levels[:8]:
            try:
                f = float(v)
            except (TypeError, ValueError):
                f = 0.0
            if f <= 1.0:  # normalized magnitude -> bar height
                f *= 31
            bands.append(max(0, min(31, int(round(f)))))
        bands += [0] * (8 - len(bands))

        self._arm_idle()
        if self._busy:
            return None  # drop: stay real-time rather than queue stale frames
        self._busy = True
        try:
            await self._data.client.write_spectrum(protocol.rhythm_frame(bands))
        except Exception as err:  # noqa: BLE001 — never fail the webhook
            _LOGGER.debug("Spectrum frame write failed: %s", err)
        finally:
            self._busy = False
        return None

    @callback
    def _arm_idle(self) -> None:
        if self._cancel_idle is not None:
            self._cancel_idle()
        self._active = True
        self._cancel_idle = async_call_later(
            self._hass, IDLE_REVERT_SECONDS, self._on_idle
        )

    @callback
    def _on_idle(self, _now) -> None:
        self._cancel_idle = None
        if self._active:
            self._active = False
            self._hass.async_create_task(self._revert())

    async def _revert(self) -> None:
        try:
            await self._data.client.show_album()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Spectrum revert to album failed: %s", err)
