"""Assistant de configuration : tout se choisit dans des listes déroulantes."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_EXTERIEUR, CONF_MAX, CONF_MIN, CONF_TEMPERATURE, CONF_TETES, DOMAIN, MAX_DEFAUT, MIN_DEFAUT, SUBENTRY_PIECE,
)


class ConfortConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Confort ressenti", data={})
        return self.async_show_form(step_id="user")

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_PIECE: PieceSubentryFlow}


def _schema(defaut: dict[str, Any] | None = None, avec_nom: bool = True) -> vol.Schema:
    d = defaut or {}

    def req(cle: str, val: Any = None):
        return vol.Required(cle, default=val) if val is not None else vol.Required(cle)

    def opt(cle: str, val: Any = None):
        return vol.Optional(cle, description={"suggested_value": val})

    champs: dict[Any, Any] = {}
    if avec_nom:
        champs[req("name", d.get("name"))] = selector.TextSelector()
    champs[req(CONF_TEMPERATURE, d.get(CONF_TEMPERATURE))] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
    )
    champs[opt(CONF_TETES, d.get(CONF_TETES))] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="climate", multiple=True)
    )
    champs[opt(CONF_EXTERIEUR, d.get(CONF_EXTERIEUR))] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
    )
    num = selector.NumberSelector(
        selector.NumberSelectorConfig(min=5, max=30, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
    )
    champs[opt(CONF_MIN, d.get(CONF_MIN, MIN_DEFAUT))] = num
    champs[opt(CONF_MAX, d.get(CONF_MAX, MAX_DEFAUT))] = num
    return vol.Schema(champs)


def _donnees(entree: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_TEMPERATURE: entree[CONF_TEMPERATURE],
        CONF_TETES: entree.get(CONF_TETES) or [],
        CONF_EXTERIEUR: entree.get(CONF_EXTERIEUR) or None,
        CONF_MIN: float(entree.get(CONF_MIN, MIN_DEFAUT)),
        CONF_MAX: float(entree.get(CONF_MAX, MAX_DEFAUT)),
    }


class PieceSubentryFlow(ConfigSubentryFlow):
    """Ajouter / modifier une pièce. Modifier un capteur conserve l'apprentissage."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        erreurs: dict[str, str] = {}
        if user_input is not None:
            noms = {s.title.casefold() for s in self._get_entry().subentries.values()}
            if user_input["name"].strip().casefold() in noms:
                erreurs["name"] = "nom_existe"
            elif float(user_input.get(CONF_MIN, MIN_DEFAUT)) >= float(user_input.get(CONF_MAX, MAX_DEFAUT)):
                erreurs[CONF_MIN] = "min_max"
            else:
                return self.async_create_entry(title=user_input["name"].strip(), data=_donnees(user_input))
        return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors=erreurs)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        sub = self._get_reconfigure_subentry()
        if user_input is not None and float(user_input.get(CONF_MIN, MIN_DEFAUT)) >= float(user_input.get(CONF_MAX, MAX_DEFAUT)):
            defaut = {"name": sub.title, **user_input}
            return self.async_show_form(
                step_id="reconfigure", data_schema=_schema(defaut), errors={CONF_MIN: "min_max"}
            )
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(), sub, title=user_input["name"].strip(), data=_donnees(user_input)
            )
        defaut = {"name": sub.title, **sub.data}
        return self.async_show_form(step_id="reconfigure", data_schema=_schema(defaut))
