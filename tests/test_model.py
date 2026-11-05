from datetime import datetime

from custom_components.confort_ressenti.model import MAX_PAS, Piece, plage_de

H = 3600.0


def piece_a(air, n=4, t0=0.0, pas=900):
    p = Piece()
    for i in range(n):
        p.mesure(t0 + i * pas, air)
    return p


def test_plages():
    assert plage_de(datetime(2026, 1, 1, 3)) == "nuit"
    assert plage_de(datetime(2026, 1, 1, 9)) == "matin"
    assert plage_de(datetime(2026, 1, 1, 15)) == "apres_midi"
    assert plage_de(datetime(2026, 1, 1, 21)) == "soir"


def test_murs_filtre_lent():
    p = Piece()
    p.mesure(0, 20.0)
    p.mesure(3600, 24.0)  # l'air monte de 4 °C en 1 h : les murs suivent lentement
    assert 20.0 < p.murs < 21.0
    assert p.ressentie() < 24.0 * 0.6 + 21.0 * 0.4 + 0.01


def test_murs_avec_exterieur_plus_froids():
    p = Piece()
    p.mesure(0, 20.0, exterieur=0.0)
    assert p.murs < 20.0


def test_tendance():
    p = Piece()
    for i in range(6):
        p.mesure(i * 900, 20 + 0.5 * i * 0.25 * 4)  # +0,5 °C par quart d'heure... = 2 °C/h
    assert abs(p.tendance() - 2.0) < 0.05
    assert Piece().tendance() is None


def test_appui_froid_puis_chaud_encadre():
    p = piece_a(19.0)
    m = datetime(2026, 1, 1, 8)
    p.appui("froid", 10, m)
    assert p.confort_effectif("matin") > 19.0
    p2 = piece_a(23.0)
    p.echantillons, p.murs = p2.echantillons, 23.0
    p.appui("chaud", 20, m)
    c = p.confort_effectif("matin")
    assert 19.0 < c < 23.0


def test_dernier_appui_gagne():
    p = piece_a(21.0)
    m = datetime(2026, 1, 1, 8)
    p.appui("chaud", 10, m)
    p.appui("froid", 20, m)  # même température : « froid » invalide « chaud » incohérent
    pl = p.plages["matin"]
    assert pl.froid is not None and pl.chaud is None


def test_pas_limite():
    p = piece_a(15.0)
    ev = p.appui("froid", 10, datetime(2026, 1, 1, 8))
    assert abs(ev["confort_apres"] - ev["confort_avant"]) <= MAX_PAS + 1e-9


def test_annuler():
    p = piece_a(19.0)
    p.appui("froid", 10, datetime(2026, 1, 1, 8))
    assert p.annuler()
    assert p.plages["matin"].appuis == 0 and p.plages["matin"].froid is None
    assert not p.annuler()


def test_ressenti_mots_et_explication():
    p = piece_a(20.0)
    assert p.ressenti("matin")[0] == "bien"
    p2 = piece_a(16.0)
    assert p2.ressenti("matin")[0] == "froid"
    assert "aucun appui" in p2.explication("matin")
    p2.appui("froid", 1, datetime(2026, 1, 1, 8))
    assert "1 appui" in p2.explication("matin")


def test_persistance_aller_retour():
    p = piece_a(19.0)
    p.appui("froid", 10, datetime(2026, 1, 1, 8))
    q = Piece.from_dict(p.to_dict())
    assert q.plages["matin"].froid == p.plages["matin"].froid
    assert q.murs == p.murs and q.appuis == p.appuis


def test_confiance_monte_avec_deux_bornes():
    p = piece_a(19.0)
    m = datetime(2026, 1, 1, 8)
    assert p.confiance("matin") == 0
    p.appui("froid", 1, m)
    c1 = p.confiance("matin")
    p.echantillons, p.murs = piece_a(21.0).echantillons, 21.0
    p.appui("chaud", 2, m)
    assert p.confiance("matin") > c1


def test_consigne_air_compense_les_murs():
    from custom_components.confort_ressenti.model import POIDS_AIR
    p = piece_a(20.0)
    p.murs = 18.0                      # murs frais -> demander un air plus chaud
    p.appui("froid", 1, datetime(2026, 1, 1, 8))
    conf = p.confort_effectif("matin")
    c = p.consigne_air("matin", 10, 30)
    assert c > conf - 1e-9
    p.murs = 24.0                      # murs chauds -> air plus bas
    assert p.consigne_air("matin", 10, 30) < c


def test_consigne_bornee_et_arrondie():
    p = piece_a(20.0)
    p.appui("froid", 1, datetime(2026, 1, 1, 8))
    assert p.consigne_air("matin", 10, 30) * 2 == round(p.consigne_air("matin", 10, 30) * 2)
    assert p.consigne_air("matin", 25, 26) == 25.0     # min de la pièce
    assert p.consigne_air("matin", 10, 15) == 15.0     # max de la pièce
    p.murs = -30.0                                     # cas extrême : écart limité à 1,5 °C du confort
    assert p.consigne_air("matin", 0, 40) <= p.confort_effectif("matin") + 1.5 + 0.25


def test_fiable_et_persistance_pilotage():
    p = piece_a(20.0)
    assert not p.fiable("matin")
    p.appui("froid", 1, datetime(2026, 1, 1, 8))
    assert p.fiable("matin") and not p.fiable("soir")
    p.pilotage_actif = True
    p.derniere_commande = {"ts": 1, "cible": 20.5, "tetes": ["climate.x"]}
    q = Piece.from_dict(p.to_dict())
    assert q.pilotage_actif and q.derniere_commande["cible"] == 20.5
    assert Piece().pilotage_actif is False   # désactivé par défaut
