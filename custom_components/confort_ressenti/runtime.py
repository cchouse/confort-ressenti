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
    CONF_EAU,
    CONF_SEUIL_ARRET,
    CONF_SEUIL_MARCHE,
    SEUIL_ARRET_DEFAUT,
    SEUIL_MARCHE_DEFAUT,
    CONF_EXTERIEUR,
    CONF_MAX,
    CONF_MIN,
    CONF_TEMPERATURE,
    MAX_DEFAUT,
    MIN_DEFAUT,
    CONF_TETES,
    DOMAIN,
    INTERVALLE_MAJ_S,
    SIGNAL_MAJ,
    STOCKAGE_VERSION,
)
from .model import PLAGES_LIBELLES, Piece, plage_de

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

    def __init__(self, hass: HomeAssistant, sub: ConfigSubentry, options: dict | None = None) -> None:
        self.hass = hass
        self.options = dict(options or {})
        self.chauffage: bool | None = None
        self.eau: float | None = None
        self.sub_id = sub.subentry_id
        self.nom = sub.title
        self.cfg = dict(sub.data)
        self.store: Store = Store(hass, STOCKAGE_VERSION, f"{DOMAIN}.{self.sub_id}")
        self.piece = Piece()
        self._unsubs: list[Callable[[], None]] = []
        self.capteur_ok = False
        self.cmin = float(self.cfg.get(CONF_MIN, MIN_DEFAUT))
        self.cmax = float(self.cfg.get(CONF_MAX, MAX_DEFAUT))
        self.consigne: float | None = None
        self.raison = "En attente d'une mesure."

    @property
    def signal(self) -> str:
        return SIGNAL_MAJ.format(self.sub_id)

    async def async_demarrer(self) -> None:
        self.piece = Piece.from_dict(await self.store.async_load())
        ids = [self.cfg[CONF_TEMPERATURE]]
        if self.cfg.get(CONF_EXTERIEUR):
            ids.append(self.cfg[CONF_EXTERIEUR])
        if self.options.get(CONF_EAU):
            ids.append(self.options[CONF_EAU])
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
    def _maj_chauffage(self) -> None:
        """Chauffage en service si l'eau dépasse le seuil haut ; hors service sous le seuil bas ; entre les deux on garde l'état précédent (pas de clignotement)."""
        eid = self.options.get(CONF_EAU)
        if not eid:
            self.eau, self.chauffage = None, None
            return
        self.eau = _lire(self.hass, eid)
        if self.eau is None:
            self.chauffage = None
            return
        haut = float(self.options.get(CONF_SEUIL_MARCHE, SEUIL_MARCHE_DEFAUT))
        bas = float(self.options.get(CONF_SEUIL_ARRET, SEUIL_ARRET_DEFAUT))
        if self.eau > haut:
            self.chauffage = True
        elif self.eau < bas:
            self.chauffage = False
        elif self.chauffage is None:
            self.chauffage = self.eau >= (haut + bas) / 2

    @callback
    def _mesurer(self) -> None:
        self._maj_chauffage()
        air = _lire(self.hass, self.cfg[CONF_TEMPERATURE])
        self.capteur_ok = air is not None
        if air is not None:
            ext = _lire(self.hass, self.cfg.get(CONF_EXTERIEUR))
            self.piece.mesure(dt_util.utcnow().timestamp(), air, ext)
            self._sauver()
        self._evaluer()
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
        self._evaluer(force=True)
        self._notifier()

    @callback
    def annuler(self) -> None:
        if self.piece.annuler():
            self._sauver()
            self._evaluer(force=True)
            self._notifier()

    @callback
    def definir_apprentissage(self, actif: bool) -> None:
        self.piece.apprentissage_actif = actif
        self._sauver()
        self._notifier()

    # ---- lecture ----
    def plage_actuelle(self) -> str:
        return plage_de(dt_util.now())

    @callback
    def definir_pilotage(self, actif: bool) -> None:
        self.piece.pilotage_actif = actif
        self._sauver()
        self._evaluer(force=True)
        self._notifier()

    # ---- pilotage des têtes ----
    @callback
    def _evaluer(self, force: bool = False) -> None:
        """Calcule la consigne d'air recommandée et, si le pilotage est actif, l'envoie aux têtes.

        Garde-fous : pilotage désactivé par défaut ; au moins un appui dans la plage ; capteur vivant ;
        consigne bornée (min/max de la pièce, ±1,5 °C du confort appris) ; on n'envoie que si la
        recommandation a CHANGÉ (un réglage manuel sur la tête est donc respecté jusqu'au prochain
        changement de recommandation) ; têtes éteintes ou indisponibles ignorées.
        """
        p, nom = self.piece, self.plage_actuelle()
        if p.air() is None:
            self.consigne, self.raison = None, "En attente d'une mesure."
            return
        cible = p.consigne_air(nom, self.cmin, self.cmax)
        self.consigne = cible
        tetes = self.cfg.get(CONF_TETES) or []
        plage = PLAGES_LIBELLES[nom].split(" (")[0].lower()
        if not p.pilotage_actif:
            self.raison = f"Pilotage désactivé : je recommande {_v(cible)} °C sans rien envoyer."
            return
        if not tetes:
            self.raison = "Aucune tête choisie pour cette pièce."
            return
        if not p.fiable(nom):
            self.raison = f"Pas encore d'appui pour {plage} : je ne commande pas les têtes."
            return
        if not self.capteur_ok:
            self.raison = "Capteur de température muet : je ne change rien."
            return
        derniere = (p.derniere_commande or {}).get("cible")
        if not force and derniere is not None and abs(derniere - cible) < 1e-9:
            self.raison = f"Têtes réglées sur {_v(cible)} °C."
            return
        envoyees = []
        for eid in tetes:
            st = self.hass.states.get(eid)
            if st is None or st.state in ("unavailable", "unknown", "off"):
                continue
            c = cible
            lo, hi = st.attributes.get("min_temp"), st.attributes.get("max_temp")
            if isinstance(lo, (int, float)):
                c = max(c, float(lo))
            if isinstance(hi, (int, float)):
                c = min(c, float(hi))
            actuelle = st.attributes.get("temperature")
            if isinstance(actuelle, (int, float)) and abs(actuelle - c) < 0.25:
                envoyees.append(eid)   # déjà bonne
                continue
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "climate", "set_temperature", {"entity_id": eid, "temperature": c}, blocking=False
                )
            )
            envoyees.append(eid)
        murs = p.murs if p.murs is not None else p.air()
        if envoyees:
            p.derniere_commande = {"ts": dt_util.utcnow().timestamp(), "cible": cible, "tetes": envoyees}
            self.raison = (
                f"Consigne {_v(cible)} °C envoyée : confort appris {_v(p.confort_effectif(nom))} °C ({plage}), "
                f"murs estimés {_v(murs)} °C."
            )
            self._sauver()
        else:
            self.raison = "Aucune tête disponible (éteinte ou injoignable) : rien envoyé."


def _v(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")
