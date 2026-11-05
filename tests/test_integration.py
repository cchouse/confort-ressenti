import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.confort_ressenti.const import (
    CONF_EXTERIEUR, CONF_TEMPERATURE, CONF_TETES, DOMAIN, SUBENTRY_PIECE,
)

CAPTEUR = "sensor.chambre_temperature"


def eid(hass, entry, domaine, cle, piece=0):
    """Id d'entité retrouvé par identifiant unique (indépendant de la langue)."""
    from homeassistant.helpers import entity_registry as er
    sub = list(entry.subentries.values())[piece]
    return er.async_get(hass).async_get_entity_id(domaine, DOMAIN, f"{sub.subentry_id}_{cle}")



async def _installer(hass):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert r["type"] is FlowResultType.FORM
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    return hass.config_entries.async_entries(DOMAIN)[0]


async def _ajouter_piece(hass, entry, nom="Chambre parentale", capteur=CAPTEUR):
    r = await hass.config_entries.subentries.async_init((entry.entry_id, SUBENTRY_PIECE), context={"source": SOURCE_USER})
    assert r["type"] is FlowResultType.FORM
    r = await hass.config_entries.subentries.async_configure(
        r["flow_id"], {"name": nom, CONF_TEMPERATURE: capteur, CONF_TETES: []}
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    await hass.async_block_till_done()


async def test_installation_et_une_seule_instance(hass):
    await _installer(hass)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert r["type"] is FlowResultType.ABORT


async def test_ajout_piece_cree_les_entites(hass):
    hass.states.async_set(CAPTEUR, "19.0")
    entry = await _installer(hass)
    await _ajouter_piece(hass, entry)
    for d, c in (("sensor","ressenti"),("sensor","confort"),("sensor","murs"),("sensor","tendance"),("sensor","confiance"),
                 ("button","trop_froid"),("button","trop_chaud"),("button","annuler"),("switch","apprentissage")):
        assert eid(hass, entry, d, c), (d, c)
    st = hass.states.get(eid(hass, entry, "sensor", "ressenti"))
    assert st is not None and st.attributes["temperature_air"] == 19.0
    assert st.attributes["boutons"]["trop_froid"]


async def test_appui_apprend_et_se_voit(hass):
    hass.states.async_set(CAPTEUR, "18.0")
    entry = await _installer(hass)
    await _ajouter_piece(hass, entry)
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "trop_froid")}, blocking=True)
    st = hass.states.get(eid(hass, entry, "sensor", "ressenti"))
    assert len(st.attributes["appuis"]) == 1
    assert st.attributes["confort"] > 18.0
    assert any(p["appuis"] == 1 for p in st.attributes["plages"])
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "annuler")}, blocking=True)
    assert len(hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["appuis"]) == 0


async def test_pause_apprentissage(hass):
    hass.states.async_set(CAPTEUR, "18.0")
    entry = await _installer(hass)
    await _ajouter_piece(hass, entry)
    await hass.services.async_call("switch", "turn_off", {"entity_id": eid(hass, entry, "switch", "apprentissage")}, blocking=True)
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "trop_froid")}, blocking=True)
    assert len(hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["appuis"]) == 0


async def test_changer_capteur_conserve_apprentissage(hass):
    hass.states.async_set(CAPTEUR, "18.0")
    hass.states.async_set("sensor.autre", "18.0")
    entry = await _installer(hass)
    await _ajouter_piece(hass, entry)
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "trop_froid")}, blocking=True)
    sub = next(iter(entry.subentries.values()))
    r = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_PIECE), context={"source": "reconfigure", "subentry_id": sub.subentry_id}
    )
    r = await hass.config_entries.subentries.async_configure(
        r["flow_id"], {"name": "Chambre parentale", CONF_TEMPERATURE: "sensor.autre"}
    )
    assert r["type"] is FlowResultType.ABORT, r
    await hass.async_block_till_done()
    st = hass.states.get(eid(hass, entry, "sensor", "ressenti"))
    assert len(st.attributes["appuis"]) == 1   # apprentissage conservé
    hass.states.async_set("sensor.autre", "19.5")
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["temperature_air"] == 19.5


async def test_deux_pieces_independantes(hass):
    hass.states.async_set(CAPTEUR, "18.0")
    hass.states.async_set("sensor.salon_t", "22.0")
    entry = await _installer(hass)
    await _ajouter_piece(hass, entry)
    await _ajouter_piece(hass, entry, "Salon", "sensor.salon_t")
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "trop_froid")}, blocking=True)
    assert len(hass.states.get(eid(hass, entry, "sensor", "ressenti", 1)).attributes["appuis"]) == 0
    assert len(hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["appuis"]) == 1


async def test_carte_servie(hass, hass_client):
    entry = await _installer(hass)
    c = await hass_client()
    r = await c.get("/confort_ressenti/confort-ressenti-card.js")
    assert r.status == 200
