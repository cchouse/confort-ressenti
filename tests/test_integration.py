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


TETE = "climate.tete_chambre"


async def _piece_avec_tete(hass, cmin=16.0, cmax=24.0, etat_tete="heat"):
    from pytest_homeassistant_custom_component.common import async_mock_service
    appels = async_mock_service(hass, "climate", "set_temperature")
    hass.states.async_set(CAPTEUR, "18.0")
    hass.states.async_set(TETE, etat_tete, {"temperature": 17.0, "min_temp": 5, "max_temp": 30})
    entry = await _installer(hass)
    r = await hass.config_entries.subentries.async_init((entry.entry_id, SUBENTRY_PIECE), context={"source": SOURCE_USER})
    r = await hass.config_entries.subentries.async_configure(
        r["flow_id"], {"name": "Chambre parentale", CONF_TEMPERATURE: CAPTEUR, CONF_TETES: [TETE],
                       "consigne_min": cmin, "consigne_max": cmax})
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    await hass.async_block_till_done()
    return entry, appels


async def _presser(hass, entry, cle):
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", cle)}, blocking=True)
    await hass.async_block_till_done()


async def _pilotage(hass, entry, on):
    await hass.services.async_call("switch", "turn_on" if on else "turn_off",
                                   {"entity_id": eid(hass, entry, "switch", "pilotage")}, blocking=True)
    await hass.async_block_till_done()


async def test_pilotage_desactive_par_defaut_rien_envoye(hass):
    entry, appels = await _piece_avec_tete(hass)
    st = hass.states.get(eid(hass, entry, "switch", "pilotage"))
    assert st.state == "off"
    await _presser(hass, entry, "trop_froid")
    assert appels == []
    a = hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["pilotage"]
    assert a["actif"] is False and a["consigne"] is not None and "recommande" in a["raison"]


async def test_pilotage_actif_envoie_la_consigne(hass):
    entry, appels = await _piece_avec_tete(hass)
    await _presser(hass, entry, "trop_froid")
    await _pilotage(hass, entry, True)
    assert len(appels) == 1
    d = appels[0].data
    assert d["entity_id"] == [TETE] or d["entity_id"] == TETE
    assert 16.0 <= d["temperature"] <= 24.0 and d["temperature"] * 2 == round(d["temperature"] * 2)
    a = hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["pilotage"]
    assert a["derniere"]["cible"] == d["temperature"] and "envoyée" in a["raison"]


async def test_pilotage_attend_un_appui(hass):
    entry, appels = await _piece_avec_tete(hass)
    await _pilotage(hass, entry, True)          # aucun appui encore : on ne commande pas
    assert appels == []
    a = hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["pilotage"]
    assert "Pas encore d'appui" in a["raison"]


async def test_pilotage_respecte_min_max(hass):
    entry, appels = await _piece_avec_tete(hass, cmin=22.0, cmax=22.5)
    await _presser(hass, entry, "trop_froid")
    await _pilotage(hass, entry, True)
    assert appels and 22.0 <= appels[-1].data["temperature"] <= 22.5


async def test_pilotage_reglage_manuel_respecte_puis_desactivation(hass):
    entry, appels = await _piece_avec_tete(hass)
    await _presser(hass, entry, "trop_froid")
    await _pilotage(hass, entry, True)
    n = len(appels)
    hass.states.async_set(CAPTEUR, "18.1")      # simple mesure : la recommandation n'a pas changé
    await hass.async_block_till_done()
    assert len(appels) == n                      # pas de renvoi : un réglage manuel serait respecté
    await _pilotage(hass, entry, False)
    n = len(appels)
    await _presser(hass, entry, "trop_froid")
    assert len(appels) == n                      # désactivé : plus rien d'envoyé


async def test_pilotage_tete_eteinte_ignoree(hass):
    entry, appels = await _piece_avec_tete(hass, etat_tete="off")
    await _presser(hass, entry, "trop_froid")
    await _pilotage(hass, entry, True)
    assert appels == []
    a = hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["pilotage"]
    assert "Aucune tête disponible" in a["raison"]


async def test_min_superieur_max_refuse(hass):
    entry = await _installer(hass)
    hass.states.async_set(CAPTEUR, "18.0")
    r = await hass.config_entries.subentries.async_init((entry.entry_id, SUBENTRY_PIECE), context={"source": SOURCE_USER})
    r = await hass.config_entries.subentries.async_configure(
        r["flow_id"], {"name": "X", CONF_TEMPERATURE: CAPTEUR, "consigne_min": 25.0, "consigne_max": 20.0})
    assert r["type"] is FlowResultType.FORM and r["errors"]


async def test_pilotage_persiste_apres_rechargement(hass):
    entry, appels = await _piece_avec_tete(hass)
    await _presser(hass, entry, "trop_froid")
    await _pilotage(hass, entry, True)
    n = len(appels)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, entry, "switch", "pilotage")).state == "on"
    assert len(appels) == n                      # pas de renvoi inutile au redémarrage


async def test_formulaires_serialisables_comme_l_interface(hass):
    import voluptuous_serialize
    from homeassistant.helpers import config_validation as cv
    hass.states.async_set(CAPTEUR, "18.0")
    entry = await _installer(hass)
    r = await hass.config_entries.subentries.async_init((entry.entry_id, SUBENTRY_PIECE), context={"source": SOURCE_USER})
    voluptuous_serialize.convert(r["data_schema"], custom_serializer=cv.custom_serializer)


async def test_bouton_je_suis_bien_pilote_les_tetes(hass):
    from pytest_homeassistant_custom_component.common import async_mock_service
    appels = async_mock_service(hass, "climate", "set_temperature")
    hass.states.async_set(CAPTEUR, "20.5")
    hass.states.async_set(TETE, "heat", {"temperature": 17.0, "min_temp": 5, "max_temp": 30})
    entry = await _installer(hass)
    r = await hass.config_entries.subentries.async_init((entry.entry_id, SUBENTRY_PIECE), context={"source": SOURCE_USER})
    r = await hass.config_entries.subentries.async_configure(
        r["flow_id"], {"name": "Chambre parentale", CONF_TEMPERATURE: CAPTEUR, CONF_TETES: [TETE]})
    await hass.async_block_till_done()
    assert eid(hass, entry, "button", "bien")
    await _pilotage(hass, entry, True)
    assert appels == []                                   # aucun appui : on ne commande pas
    await _presser(hass, entry, "bien")                   # « je suis bien » seul suffit
    st = hass.states.get(eid(hass, entry, "sensor", "ressenti"))
    assert st.attributes["appuis"][0]["sens"] == "bien" and st.attributes["confiance"] > 0
    assert appels and 19.0 <= appels[-1].data["temperature"] <= 22.0
    assert hass.states.get(eid(hass, entry, "sensor", "ressenti")).attributes["boutons"]["bien"]
