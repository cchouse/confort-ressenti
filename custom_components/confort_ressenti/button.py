from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import PieceEntity
from .runtime import PieceRuntime


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    for sub_id, rt in entry.runtime_data.items():
        async_add_entities(
            [Bouton(rt, "trop_froid", "froid"), Bouton(rt, "trop_chaud", "chaud"), Annuler(rt)],
            config_subentry_id=sub_id,
        )


class Bouton(PieceEntity, ButtonEntity):
    def __init__(self, rt: PieceRuntime, cle: str, sens: str) -> None:
        super().__init__(rt, cle)
        self._sens = sens

    async def async_press(self) -> None:
        self.rt.appui(self._sens)


class Annuler(PieceEntity, ButtonEntity):
    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "annuler")

    async def async_press(self) -> None:
        self.rt.annuler()
