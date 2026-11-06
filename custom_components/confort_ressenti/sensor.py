"""Capteurs : ressenti (avec tout le détail pour la carte), confort appris, murs, tendance, confiance."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import PieceEntity
from .model import RESSENTI_LIBELLES, SEUIL_TENDANCE
from .runtime import PieceRuntime


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    for sub_id, rt in entry.runtime_data.items():
        async_add_entities(
            [
                RessentiSensor(rt),
                ConfortSensor(rt),
                MursSensor(rt),
                TendanceSensor(rt),
                ConfianceSensor(rt),
                ConsigneSensor(rt),
            ],
            config_subentry_id=sub_id,
        )


class RessentiSensor(PieceEntity, SensorEntity):
    """État = mot (froid / frais / bien / doux / chaud). Attributs = tout ce que montre la carte."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(RESSENTI_LIBELLES)
    _unrecorded_attributes = frozenset(
        {"plages", "historique", "appuis", "explication", "boutons", "libelle", "temperature_ressentie",
         "pilotage", "chauffage", "temperature_air", "murs_estimes", "confort", "tendance", "confiance", "plage", "ecart"}
    )

    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "ressenti")

    @property
    def native_value(self) -> str | None:
        return self.rt.piece.ressenti(self.rt.plage_actuelle())[0]

    def _boutons(self) -> dict[str, str | None]:
        reg = er.async_get(self.hass)
        return {
            cle: reg.async_get_entity_id("button", DOMAIN, f"{self.rt.sub_id}_{cle}")
            for cle in ("trop_froid", "bien", "trop_chaud", "annuler")
        } | {"apprentissage": reg.async_get_entity_id("switch", DOMAIN, f"{self.rt.sub_id}_apprentissage"),
            "pilotage": reg.async_get_entity_id("switch", DOMAIN, f"{self.rt.sub_id}_pilotage")}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        p, nom = self.rt.piece, self.rt.plage_actuelle()
        cle, delta = p.ressenti(nom)
        r = p.ressentie()
        t = p.tendance()
        return {
            "libelle": RESSENTI_LIBELLES.get(cle) if cle else None,
            "piece": self.rt.nom,
            "plage": nom,
            "capteur_ok": self.rt.capteur_ok,
            "temperature_air": p.air(),
            "murs_estimes": None if p.murs is None else round(p.murs, 2),
            "temperature_ressentie": None if r is None else round(r, 2),
            "confort": round(p.confort_effectif(nom), 2),
            "ecart": None if delta is None else round(delta, 2),
            "tendance": None if t is None else round(t, 2),
            "tendance_seuil": SEUIL_TENDANCE,
            "confiance": p.confiance_globale(),
            "apprentissage_actif": p.apprentissage_actif,
            "explication": p.explication(nom, self.rt.chauffage, self.rt.eau),
            "chauffage": {
                "configure": bool(self.rt.options.get("capteur_eau")),
                "en_service": self.rt.chauffage,
                "eau": self.rt.eau,
                "seuil_marche": self.rt.options.get("seuil_marche", 55.0),
                "seuil_arret": self.rt.options.get("seuil_arret", 47.0),
            },
            "plages": p.resume_apprentissage(nom),
            "historique": [[int(ts), round(a, 2), round(m, 2)] for ts, a, m in p.historique],
            "appuis": p.appuis[-8:][::-1],
            "peut_annuler": p.annulation is not None,
            "pilotage": {
                "actif": p.pilotage_actif,
                "consigne": self.rt.consigne,
                "raison": self.rt.raison,
                "min": self.rt.cmin,
                "max": self.rt.cmax,
                "nb_tetes": len(self.rt.cfg.get("tetes") or []),
                "derniere": p.derniere_commande,
            },
            "boutons": self._boutons(),
        }


class _Temp(PieceEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1


class ConfortSensor(_Temp):
    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "confort")

    @property
    def native_value(self) -> float:
        return round(self.rt.piece.confort_effectif(self.rt.plage_actuelle()), 2)


class MursSensor(_Temp):
    _attr_entity_registry_enabled_default = True

    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "murs")

    @property
    def native_value(self) -> float | None:
        m = self.rt.piece.murs
        return None if m is None else round(m, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"nature": "estimation (filtre de la température de l'air), pas une mesure"}


class TendanceSensor(PieceEntity, SensorEntity):
    _attr_native_unit_of_measurement = "°C/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "tendance")

    @property
    def native_value(self) -> float | None:
        t = self.rt.piece.tendance()
        return None if t is None else round(t, 2)


class ConfianceSensor(PieceEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "confiance")

    @property
    def native_value(self) -> int:
        return round(self.rt.piece.confiance_globale() * 100)


class ConsigneSensor(_Temp):
    """Consigne d'air recommandée (celle qui est envoyée aux têtes quand le pilotage est actif)."""

    _attr_state_class = None

    def __init__(self, rt: PieceRuntime) -> None:
        super().__init__(rt, "consigne")

    @property
    def native_value(self) -> float | None:
        return self.rt.consigne

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"pilotage_actif": self.rt.piece.pilotage_actif, "raison": self.rt.raison}
