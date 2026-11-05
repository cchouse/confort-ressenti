"""Entité de base : une pièce = un appareil."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .runtime import PieceRuntime


class PieceEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, rt: PieceRuntime, cle: str) -> None:
        self.rt = rt
        self._cle = cle
        self._attr_translation_key = cle
        self._attr_unique_id = f"{rt.sub_id}_{cle}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, rt.sub_id)}, name=rt.nom, manufacturer="B-Home", model="Confort ressenti"
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, self.rt.signal, self._maj))

    @callback
    def _maj(self) -> None:
        self.async_write_ha_state()
