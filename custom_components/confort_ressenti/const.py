"""Constantes de l'intégration Confort ressenti."""
DOMAIN = "confort_ressenti"
SUBENTRY_PIECE = "piece"

CONF_TEMPERATURE = "capteur_temperature"
CONF_TETES = "tetes"
CONF_EXTERIEUR = "capteur_exterieur"
CONF_MIN = "consigne_min"
CONF_MAX = "consigne_max"
MIN_DEFAUT = 16.0
MAX_DEFAUT = 24.0

SIGNAL_MAJ = f"{DOMAIN}_maj_{{}}"          # formaté avec l'id de sous-entrée
INTERVALLE_MAJ_S = 300
STOCKAGE_VERSION = 1

URL_CARTE = "/confort_ressenti/confort-ressenti-card.js"
VERSION = "0.3.0"
