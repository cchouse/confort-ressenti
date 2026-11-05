"""Modèle d'apprentissage du confort ressenti (pur Python, sans Home Assistant).

Principe
--------
* La journée est découpée en 4 plages (nuit, matin, après-midi, soir).
* Chaque appui « trop froid » / « trop chaud » pose une borne pour la plage en cours :
  - « trop froid » à T  -> le confort est AU-DESSUS de T
  - « trop chaud » à T  -> le confort est EN-DESSOUS de T
  - conflit : le dernier appui gagne (la borne contraire devenue incohérente est retirée).
* La température prise en compte est la température RESSENTIE (opérative) :
  mélange de l'air (capteur) et d'une ESTIMATION de la température des murs
  (filtre passe-bas de l'air, tau ≈ 8 h). Ce n'est pas une mesure : c'est étiqueté
  « estimé » partout dans l'interface.
* La consigne apprise ne bouge jamais de plus de MAX_PAS par appui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

PLAGES = ("nuit", "matin", "apres_midi", "soir")
PLAGES_LIBELLES = {
    "nuit": "Nuit (0 h – 6 h)",
    "matin": "Matin (6 h – 12 h)",
    "apres_midi": "Après-midi (12 h – 18 h)",
    "soir": "Soir (18 h – 24 h)",
}

CONFORT_PAR_DEFAUT = 20.0
MARGE_UNE_BORNE = 0.7      # confort = borne ± marge quand une seule borne est connue
MAX_PAS = 1.0              # variation maximale du confort par appui (°C)
PEREMPTION_JOURS = 60      # une borne plus vieille que ça compte pour moins
ECART_CONSIGNE_MAX = 1.5   # la consigne d'air ne s'écarte jamais de plus de 1,5 °C du confort appris
PAS_CONSIGNE = 0.5
TAU_MURS_H = 8.0           # constante de temps (heures) de l'estimation des murs
POIDS_AIR = 0.6            # température ressentie = 0,6 air + 0,4 murs
ECART_MURS_EXTERIEUR = 0.08  # les murs sont un peu plus froids que l'air quand il gèle dehors
HISTO_PAS_S = 15 * 60
HISTO_MAX = 96             # 24 h à 15 min
APPUIS_MAX = 30
REGRESSION_FENETRE_S = 3 * 3600
SEUIL_TENDANCE = 0.3       # °C/h

RESSENTI_SEUILS = ((-2.0, "froid"), (-0.7, "frais"), (0.7, "bien"), (2.0, "doux"))  # sinon "chaud"
RESSENTI_LIBELLES = {
    "froid": "Froid",
    "frais": "Un peu frais",
    "bien": "Bien",
    "doux": "Un peu chaud",
    "chaud": "Chaud",
}


def plage_de(dt: datetime) -> str:
    h = dt.hour
    if h < 6:
        return "nuit"
    if h < 12:
        return "matin"
    if h < 18:
        return "apres_midi"
    return "soir"


def _virgule(x: float, n: int = 1) -> str:
    return f"{x:.{n}f}".replace(".", ",")


@dataclass
class Plage:
    froid: float | None = None        # borne basse : le confort est au-dessus
    froid_ts: float | None = None
    chaud: float | None = None        # borne haute : le confort est en dessous
    chaud_ts: float | None = None
    appuis: int = 0
    confort: float | None = None      # dernier confort retenu (sert à limiter le pas)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Plage":
        p = cls()
        for k in p.__dict__:
            if k in d:
                setattr(p, k, d[k])
        return p


@dataclass
class Piece:
    plages: dict[str, Plage] = field(default_factory=lambda: {k: Plage() for k in PLAGES})
    murs: float | None = None
    murs_ts: float | None = None
    echantillons: list[tuple[float, float]] = field(default_factory=list)  # (ts, air) récents
    historique: list[tuple[float, float, float]] = field(default_factory=list)  # (ts, air, murs)
    appuis: list[dict[str, Any]] = field(default_factory=list)
    annulation: dict[str, Any] | None = None
    apprentissage_actif: bool = True
    pilotage_actif: bool = False      # envoi réel des consignes aux têtes (désactivé par défaut)
    derniere_commande: dict[str, Any] | None = None

    # ---------- persistance ----------
    def to_dict(self) -> dict[str, Any]:
        return {
            "plages": {k: v.to_dict() for k, v in self.plages.items()},
            "murs": self.murs,
            "murs_ts": self.murs_ts,
            "historique": [list(x) for x in self.historique],
            "appuis": self.appuis,
            "annulation": self.annulation,
            "apprentissage_actif": self.apprentissage_actif,
            "pilotage_actif": self.pilotage_actif,
            "derniere_commande": self.derniere_commande,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Piece":
        p = cls()
        if not d:
            return p
        for k, v in (d.get("plages") or {}).items():
            if k in p.plages:
                p.plages[k] = Plage.from_dict(v)
        p.murs = d.get("murs")
        p.murs_ts = d.get("murs_ts")
        p.historique = [tuple(x) for x in d.get("historique", [])][-HISTO_MAX:]
        p.appuis = list(d.get("appuis", []))[-APPUIS_MAX:]
        p.annulation = d.get("annulation")
        p.apprentissage_actif = d.get("apprentissage_actif", True)
        p.pilotage_actif = d.get("pilotage_actif", False)
        p.derniere_commande = d.get("derniere_commande")
        return p

    # ---------- mesures ----------
    def mesure(self, ts: float, air: float, exterieur: float | None = None) -> None:
        """Enregistre une mesure d'air et met à jour l'estimation des murs."""
        self.echantillons.append((ts, air))
        limite = ts - REGRESSION_FENETRE_S
        self.echantillons = [e for e in self.echantillons if e[0] >= limite][-200:]
        cible = air if exterieur is None else air - ECART_MURS_EXTERIEUR * (air - exterieur)
        if self.murs is None or self.murs_ts is None:
            self.murs = cible
        else:
            dt_h = max(0.0, (ts - self.murs_ts) / 3600.0)
            alpha = min(1.0, dt_h / TAU_MURS_H)
            self.murs += alpha * (cible - self.murs)
        self.murs_ts = ts
        if not self.historique or ts - self.historique[-1][0] >= HISTO_PAS_S:
            self.historique.append((ts, air, self.murs))
            self.historique = self.historique[-HISTO_MAX:]

    def air(self) -> float | None:
        return self.echantillons[-1][1] if self.echantillons else None

    def ressentie(self) -> float | None:
        a = self.air()
        if a is None:
            return None
        if self.murs is None:
            return a
        return POIDS_AIR * a + (1 - POIDS_AIR) * self.murs

    def tendance(self) -> float | None:
        """Pente de l'air en °C/h (régression linéaire sur 3 h), None si trop peu de données."""
        e = self.echantillons
        if len(e) < 3 or e[-1][0] - e[0][0] < 1200:
            return None
        t0 = e[0][0]
        xs = [(t - t0) / 3600.0 for t, _ in e]
        ys = [v for _, v in e]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        den = sum((x - mx) ** 2 for x in xs)
        if den == 0:
            return None
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den

    # ---------- apprentissage ----------
    def _moyenne_autres(self, nom: str) -> float | None:
        vals = [p.confort for k, p in self.plages.items() if k != nom and p.confort is not None]
        return sum(vals) / len(vals) if vals else None

    def confort(self, nom: str, maintenant_ts: float | None = None) -> float:
        p = self.plages[nom]
        c, h = p.froid, p.chaud
        if c is not None and h is not None:
            return (c + h) / 2
        if c is not None:
            return c + MARGE_UNE_BORNE
        if h is not None:
            return h - MARGE_UNE_BORNE
        autre = self._moyenne_autres(nom)
        return autre if autre is not None else CONFORT_PAR_DEFAUT

    def confiance(self, nom: str) -> float:
        p = self.plages[nom]
        if p.froid is None and p.chaud is None:
            return 0.0
        if p.froid is None or p.chaud is None:
            return 0.35
        largeur = abs(p.chaud - p.froid)
        return 0.6 + 0.4 * max(0.0, min(1.0, (3.0 - largeur) / 2.0))

    def appui(self, sens: str, ts: float, maintenant: datetime) -> dict[str, Any]:
        """sens = 'froid' | 'chaud'. Renvoie l'événement enregistré."""
        ressentie = self.ressentie()
        if ressentie is None:
            raise ValueError("pas de mesure de température")
        nom = plage_de(maintenant)
        p = self.plages[nom]
        avant = {"plage": nom, "etat": p.to_dict()}
        ancien = self.confort(nom)
        if sens == "froid":
            p.froid, p.froid_ts = ressentie, ts
            if p.chaud is not None and p.chaud <= p.froid:
                p.chaud, p.chaud_ts = None, None
        else:
            p.chaud, p.chaud_ts = ressentie, ts
            if p.froid is not None and p.froid >= p.chaud:
                p.froid, p.froid_ts = None, None
        p.appuis += 1
        nouveau = self.confort(nom)
        # limite de variation par appui
        if p.confort is not None or abs(nouveau - ancien) > MAX_PAS:
            nouveau = max(ancien - MAX_PAS, min(ancien + MAX_PAS, nouveau))
        p.confort = nouveau
        evt = {
            "ts": ts,
            "sens": sens,
            "plage": nom,
            "ressentie": round(ressentie, 2),
            "confort_avant": round(ancien, 2),
            "confort_apres": round(nouveau, 2),
        }
        self.appuis.append(evt)
        self.appuis = self.appuis[-APPUIS_MAX:]
        self.annulation = avant
        return evt

    def annuler(self) -> bool:
        if not self.annulation:
            return False
        self.plages[self.annulation["plage"]] = Plage.from_dict(self.annulation["etat"])
        if self.appuis:
            self.appuis.pop()
        self.annulation = None
        return True

    def confort_effectif(self, nom: str) -> float:
        """Confort courant (respecte le pas limité une fois initialisé)."""
        p = self.plages[nom]
        if p.confort is not None and (p.froid is not None or p.chaud is not None):
            return p.confort
        return self.confort(nom)

    def fiable(self, nom: str) -> bool:
        """Au moins un appui dans cette plage : sinon on ne commande pas les têtes."""
        return self.confiance(nom) > 0

    def consigne_air(self, nom: str, cmin: float, cmax: float) -> float:
        """Température d'AIR à demander à la tête pour que le ressenti égale le confort appris."""
        conf = self.confort_effectif(nom)
        if self.murs is None:
            cible = conf
        else:
            cible = (conf - (1 - POIDS_AIR) * self.murs) / POIDS_AIR
        cible = max(conf - ECART_CONSIGNE_MAX, min(conf + ECART_CONSIGNE_MAX, cible))
        cible = max(cmin, min(cmax, cible))
        return round(cible / PAS_CONSIGNE) * PAS_CONSIGNE

    # ---------- lecture ----------
    def ressenti(self, nom: str) -> tuple[str, float] | tuple[None, None]:
        r = self.ressentie()
        if r is None:
            return None, None
        delta = r - self.confort_effectif(nom)
        for seuil, cle in RESSENTI_SEUILS:
            if delta < seuil:
                return cle, delta
        return "chaud", delta

    def explication(self, nom: str) -> str:
        r = self.ressentie()
        a = self.air()
        if r is None or a is None:
            return "En attente d'une mesure de température."
        cle, delta = self.ressenti(nom)
        conf = self.confort_effectif(nom)
        parts = []
        murs = self.murs if self.murs is not None else a
        parts.append(
            f"L'air mesure {_virgule(a)} °C, les murs sont estimés à {_virgule(murs)} °C : "
            f"on ressent donc environ {_virgule(r)} °C."
        )
        p = self.plages[nom]
        if p.appuis == 0:
            parts.append(
                f"Je n'ai encore aucun appui pour {PLAGES_LIBELLES[nom].split(' (')[0].lower()}, "
                f"je pars de {_virgule(conf)} °C. Appuyez sur « trop froid » ou « trop chaud » "
                "pour m'apprendre votre confort."
            )
        else:
            parts.append(
                f"Votre confort appris pour ce moment de la journée est {_virgule(conf)} °C "
                f"(d'après {p.appuis} appui{'s' if p.appuis > 1 else ''})."
            )
        ecart = abs(delta)
        if cle == "bien":
            parts.append("Vous êtes dans la zone de confort.")
        elif delta < 0:
            parts.append(f"Il manque environ {_virgule(ecart)} °C pour être bien.")
        else:
            parts.append(f"C'est environ {_virgule(ecart)} °C au-dessus de votre confort.")
        t = self.tendance()
        if t is not None:
            if t > SEUIL_TENDANCE:
                parts.append(f"La pièce se réchauffe (+{_virgule(t)} °C/h).")
            elif t < -SEUIL_TENDANCE:
                parts.append(f"La pièce se refroidit ({_virgule(t)} °C/h).")
            else:
                parts.append("La température est stable.")
        return " ".join(parts)

    def resume_apprentissage(self, nom_actuel: str) -> list[dict[str, Any]]:
        out = []
        for nom in PLAGES:
            p = self.plages[nom]
            out.append(
                {
                    "plage": nom,
                    "libelle": PLAGES_LIBELLES[nom],
                    "confort": round(self.confort_effectif(nom), 1),
                    "confiance": round(self.confiance(nom), 2),
                    "appuis": p.appuis,
                    "froid": None if p.froid is None else round(p.froid, 1),
                    "chaud": None if p.chaud is None else round(p.chaud, 1),
                    "actuelle": nom == nom_actuel,
                }
            )
        return out

    def confiance_globale(self) -> float:
        return round(sum(self.confiance(n) for n in PLAGES) / len(PLAGES), 2)


def maintenant_ts() -> float:
    return datetime.now(timezone.utc).timestamp()
