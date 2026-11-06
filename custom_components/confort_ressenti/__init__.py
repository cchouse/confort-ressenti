"""Confort ressenti : apprend, pièce par pièce, ce que « bien » veut dire pour vous."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, URL_CARTE, VERSION
from .runtime import PieceRuntime

PLATFORMS = ["sensor", "button", "switch", "binary_sensor"]

type ConfortConfigEntry = ConfigEntry[dict[str, PieceRuntime]]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Publie la carte Lovelace et la charge automatiquement dans l'interface."""
    chemin = Path(__file__).parent / "www" / "confort-ressenti-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(URL_CARTE, str(chemin), False)])
    add_extra_js_url(hass, f"{URL_CARTE}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfortConfigEntry) -> bool:
    runtimes: dict[str, PieceRuntime] = {}
    for sub in entry.subentries.values():
        rt = PieceRuntime(hass, sub, entry.options)
        await rt.async_demarrer()
        runtimes[sub.subentry_id] = rt
    entry.runtime_data = runtimes
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for rt in runtimes.values():
        rt.notifier()  # les boutons existent maintenant : l'attribut « boutons » du ressenti se complète
    entry.async_on_unload(entry.add_update_listener(_recharger))
    return True


async def _recharger(hass: HomeAssistant, entry: ConfortConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfortConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        for rt in entry.runtime_data.values():
            await rt.async_arreter()
    return ok
