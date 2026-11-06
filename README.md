# Confort ressenti (Home Assistant) — version 0.4.0

Apprend, pièce par pièce, ce qui est « bien » pour vous : deux boutons, **Trop froid** / **Trop chaud**.

## Installation (5 gestes)
1. Copier le dossier `confort_ressenti` dans `/config/custom_components/` (créer `custom_components` s'il n'existe pas).
2. Redémarrer Home Assistant.
3. Paramètres → Appareils et services → **Ajouter une intégration** → « Confort ressenti » → Valider.
4. Sur la fiche de l'intégration : **Ajouter une pièce** → nom + capteur de température choisi dans la liste (têtes et extérieur facultatifs).
5. Tableau de bord → Ajouter une carte → « Confort ressenti » → choisir la pièce. La carte est chargée toute seule (aucune ressource à déclarer).

Changer de capteur plus tard : menu ⋮ de la pièce → **Modifier les capteurs** ; l'apprentissage est conservé.
Autant de pièces que vous voulez, chacune apprend séparément.

## Ce que voit la carte
Ressenti en mots, température ressentie, air mesuré, **murs estimés**, tendance (°C/h), courbe 24 h, fiabilité de l'apprentissage par plage (nuit/matin/après-midi/soir), phrase « Pourquoi ? », derniers appuis, annulation.

## Pilotage des têtes (nouveau en 0.2.0)
Chaque pièce a un interrupteur **« Piloter les têtes »**, **désactivé par défaut**. Une fois activé, l'intégration envoie aux têtes choisies la consigne d'**air** qui donne le ressenti appris (elle tient compte des murs estimés), arrondie à 0,5 °C.
Garde-fous : au moins un appui dans la plage en cours ; consigne limitée au minimum/maximum de la pièce et à ±1,5 °C du confort appris ; envoi seulement quand la recommandation change (un réglage manuel sur la tête est respecté) ; têtes éteintes ou indisponibles ignorées ; capteur muet = aucun changement. Chaque envoi est expliqué en une phrase sur la carte. Le capteur « Consigne recommandée » est toujours disponible, même pilotage désactivé.

## Chauffage en service (nouveau en 0.4.0)
Sur la fiche de l'intégration, bouton ⚙ **Configurer** : choisissez dans la liste le capteur de température d'eau du circuit (ex. sortie poêle ou ballon tampon). Au-dessus de **55 °C** le chauffage est « en service », sous **47 °C** « hors service », entre les deux l'état précédent est gardé (pas de clignotement). Les deux seuils se règlent.
Effet : une entité « Chauffage en service » par pièce, une ligne sur la carte et une phrase dans « Pourquoi ce ressenti ? » (une pièce qui se refroidit chauffage coupé, c'est normal). Les consignes aux têtes restent envoyées même eau froide, pour qu'elles soient prêtes. Sans capteur d'eau, rien ne change.

## Limites de cette version
- Le pilotage est testé en simulation (29 tests), **pas encore sur de vraies têtes Aqara E1** : activez-le d'abord sur une seule pièce.
- Les murs sont une **estimation** (filtre lent de l'air), pas une mesure.
- Testée avec le banc d'essai Home Assistant 2026.2 (29 tests) et un rendu de la carte ; pas encore sur votre installation réelle. Nécessite Home Assistant ≥ 2025.3.
