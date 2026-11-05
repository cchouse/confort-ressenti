from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import PieceEntity
from .runtime import PieceRuntime


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    for sub_id, rt in entry.runtime_data.items():
        async_add_entities([Apprentissage(rt)], config_subentry_id=sub_id)


class Apprentissage(PieceEntity, SwitchEntity):
    """Met l'apprentissage en pause (ex. fenêtre ouverte, invités) sans rien perdre."""

    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "apprentissage")

    @property
    def is_on(self) -> bool:
        return self.rt.piece.apprentissage_actif

    async def async_turn_on(self, **kwargs) -> None:
        self.rt.definir_apprentissage(True)

    async def async_turn_off(self, **kwargs) -> None:
        self.rt.definir_apprentissage(False)
