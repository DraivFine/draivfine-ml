# Entraînement du modèle (à venir)

Ce dossier accueillera le pipeline d'entraînement scikit-learn/XGBoost une fois
assez de trajets labellisés disponibles (idéalement avec un feedback réel :
signalements, accidents confirmés, ou correction manuelle du score heuristique).

Tant qu'aucun fichier `model.joblib` n'existe ici, le service utilise
automatiquement le scoring heuristique (`app/services/heuristics.py`).

## Plan prévu

1. **Extraction des features** (`features.py`, à créer) : DOIT rester alignée
   avec `MLScoringModel._extraire_features` dans `app/services/ml_model.py`.
   Features candidates : nb d'événements par type, vitesse moyenne/max,
   variance de l'accélération, distance, durée, ratio temps en excès de vitesse.
2. **Labels** : score cible = score heuristique existant (bootstrap), puis
   affiné avec des labels réels (sinistres, signalements confirmés) une fois
   dispo côté module `Signalement`.
3. **Entraînement** : scikit-learn (`GradientBoostingRegressor`) ou XGBoost
   selon le volume de données.
4. **Sérialisation** : `joblib.dump(model, "training/model.joblib")`.
5. **Déploiement** : redémarrer le conteneur `moto-safety-ml` (le modèle est
   chargé une seule fois au startup, voir `app/main.py`).

## Pourquoi pas dès maintenant ?

Le MVP heuristique (seuils sur accélération/décélération/vitesse/virage)
donne déjà un score exploitable et explicable — important pour justifier une
alerte ou une suspension d'abonnement à un conducteur. Le modèle ML n'apporte
de la valeur qu'avec assez de données réelles pour dépasser en fiabilité les
heuristiques ; en attendant, il ajouterait de la complexité sans bénéfice net.
