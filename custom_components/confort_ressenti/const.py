"""Constantes de l'intégration Confort ressenti."""
DOMAIN = "confort_ressenti"
SUBENTRY_PIECE = "piece"

CONF_TEMPERATURE = "capteur_temperature"
CONF_TETES = "tetes"
CONF_EXTERIEUR = "capteur_exterieur"
CONF_EAU = "capteur_eau"
CONF_SEUIL_MARCHE = "seuil_marche"
CONF_SEUIL_ARRET = "seuil_arret"
SEUIL_MARCHE_DEFAUT = 55.0
SEUIL_ARRET_DEFAUT = 47.0
CONF_MIN = "consigne_min"
CONF_MAX = "consigne_max"
MIN_DEFAUT = 16.0
MAX_DEFAUT = 24.0

SIGNAL_MAJ = f"{DOMAIN}_maj_{{}}"          # formaté avec l'id de sous-entrée
INTERVALLE_MAJ_S = 300
STOCKAGE_VERSION = 1

URL_CARTE = "/confort_ressenti/confort-ressenti-card.js"
VERSION = "0.4.0"
