"""Exécution : une PieceRuntime par pièce (sous-entrée)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXTERIEUR,
    CONF_TEMPERATURE,
    CONF_TETES,
    DOMAIN,
    INTERVALLE_MAJ_S,
    SIGNAL_MAJ,
    STOCKAGE_VERSION,
)
from .model import Piece, plage_de

_LOGGER = logging.getLogger(__name__)


def _lire(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    st = hass.states.get(entity_id)
    if st is None or st.state in ("unknown", "unavailable", ""):
        return None
    try:
        return float(st.state)
    except ValueError:
        return None


class PieceRuntime:
    """Pont entre Home Assistant et le modèle d'apprentissage d'une pièce."""

    def __init__(self, hass: HomeAssistant, sub: ConfigSubentry) -> None:
        self.hass = hass
        self.sub_id = sub.subentry_id
        self.nom = sub.title
        self.cfg = dict(sub.data)
        self.store: Store = Store(hass, STOCKAGE_VERSION, f"{DOMAIN}.{self.sub_id}")
        self.piece = Piece()
        self._unsubs: list[Callable[[], None]] = []
        self.capteur_ok = False

    @property
    def signal(self) -> str:
        return SIGNAL_MAJ.format(self.sub_id)

    async def async_demarrer(self) -> None:
        self.piece = Piece.from_dict(await self.store.async_load())
        ids = [self.cfg[CONF_TEMPERATURE]]
        if self.cfg.get(CONF_EXTERIEUR):
            ids.append(self.cfg[CONF_EXTERIEUR])
        self._unsubs.append(async_track_state_change_event(self.hass, ids, self._changement))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._periodique, timedelta(seconds=INTERVALLE_MAJ_S))
        )
        self._mesurer()

    async def async_arreter(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        await self.store.async_save(self.piece.to_dict())

    # ---- mesures ----
    @callback
    def _changement(self, _event: Event) -> None:
        self._mesurer()

    @callback
    def _periodique(self, _now) -> None:
        self._mesurer()

    @callback
    def _mesurer(self) -> None:
        air = _lire(self.hass, self.cfg[CONF_TEMPERATURE])
        self.capteur_ok = air is not None
        if air is not None:
            ext = _lire(self.hass, self.cfg.get(CONF_EXTERIEUR))
            self.piece.mesure(dt_util.utcnow().timestamp(), air, ext)
            self._sauver()
        self._notifier()

    @callback
    def _sauver(self) -> None:
        self.store.async_delay_save(self.piece.to_dict, 30)

    @callback
    def notifier(self) -> None:
        self._notifier()

    @callback
    def _notifier(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    # ---- actions ----
    @callback
    def appui(self, sens: str) -> None:
        if not self.piece.apprentissage_actif:
            _LOGGER.info("%s : apprentissage en pause, appui ignoré", self.nom)
            return
        self.piece.appui(sens, dt_util.utcnow().timestamp(), dt_util.now())
        self._sauver()
        self._notifier()

    @callback
    def annuler(self) -> None:
        if self.piece.annuler():
            self._sauver()
            self._notifier()

    @callback
    def definir_apprentissage(self, actif: bool) -> None:
        self.piece.apprentissage_actif = actif
        self._sauver()
        self._notifier()

    # ---- lecture ----
    def plage_actuelle(self) -> str:
        return plage_de(dt_util.now())
