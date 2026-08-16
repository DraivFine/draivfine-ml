# moto-safety-ml

Microservice **FastAPI** interne pour le scoring comportemental de conduite
(MotoSafe). Appelé uniquement par le backend NestJS (worker BullMQ du module
`scoring`) via le réseau Docker interne — pas d'exposition publique.

## Architecture

```
app/
  main.py              # point d'entrée FastAPI, charge le modèle ML au startup
  config.py             # Settings (pydantic-settings), seuils heuristiques
  schemas.py             # contrats Pydantic (doivent matcher ml.client.ts côté NestJS)
  routers/
    scoring.py           # POST /score
    health.py             # GET /health
  services/
    heuristics.py         # MVP : détection d'événements par seuils physiques
    ml_model.py            # wrapper modèle entraîné (optionnel), fallback gracieux
    scorer.py               # orchestrateur : ML si dispo, sinon heuristique
training/
  README.md              # plan du futur pipeline d'entraînement scikit-learn/XGBoost
```

## Deux contrats exposés

- **`POST /scoring/predict`** — contrat de **compatibilité stricte** avec
  `src/scoring/ml-client.service.ts` déjà écrit côté NestJS. Payload et
  réponse en snake_case (`note_globale`, `niveau_risque`, `freinages_brusques`,
  `accelerations_brusques`, `exces_vitesse`, `trajectoire_anormale`), sans
  header d'auth (le client NestJS actuel n'en envoie pas). Utilise les
  **mêmes seuils heuristiques** que `heuristiques.service.ts` côté NestJS
  (voir `app/services/heuristics_compat.py`) pour que le score soit identique
  que le fallback NestJS se déclenche ou que ce service réponde.
- **`POST /score`** — contrat plus riche (liste d'événements horodatés avec
  sévérité, distance/durée calculées), protégé par `X-Internal-Api-Key`.
  Pensé pour d'éventuels futurs consommateurs (dashboard, endpoint mobile
  dédié) qui ont besoin de plus de détail que juste un score global.

## Logique de scoring (heuristique MVP)

1. Le backend NestJS envoie un lot de points capteurs (accéléro + GPS) pour un trajet.
2. Si un modèle entraîné existe (`ML_MODEL_PATH`), il est utilisé.
3. Sinon (cas MVP actuel), fallback automatique sur les heuristiques :
   - freinage / accélération brusque (norme du vecteur accéléro vs seuil)
   - excès de vitesse (vs limite du contexte + marge de tolérance)
   - virage brusque (variation de cap par seconde)
4. Chaque événement a une sévérité `[0,1]`, pondérée par type pour calculer un
   score global `[0,100]` (100 = conduite exemplaire).

Le champ `methode` dans la réponse de `/score` indique toujours si le score
vient du modèle ML ou des heuristiques — utile pour l'observabilité côté
NestJS. `/scoring/predict` n'a pas ce champ (contrat figé côté NestJS), mais
loggue la même info côté serveur.

## Lancer en local (sans Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis éditer INTERNAL_API_KEY
uvicorn app.main:app --reload --port 8000
```

## Exemple d'appel

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: change-me-generate-a-long-random-value" \
  -d '{
    "trajet_id": "trajet_123",
    "conducteur_id": "cond_456",
    "contexte": { "limite_vitesse_kmh": 60, "zone_urbaine": true },
    "points": [
      {"timestamp":"2026-08-15T10:00:00Z","accel_x":0.1,"accel_y":0.2,"accel_z":9.8,"latitude":4.05,"longitude":9.7,"vitesse_kmh":40,"cap":90},
      {"timestamp":"2026-08-15T10:00:01Z","accel_x":0.1,"accel_y":0.2,"accel_z":14.2,"latitude":4.0502,"longitude":9.7003,"vitesse_kmh":18,"cap":95}
    ]
  }'
```

## Intégration Docker Compose (backend MotoSafe)

Ton `docker-compose.yml` du backend NestJS a déjà le service `api` configuré
avec `ML_SERVICE_URL: http://ml-service:8001` et un bloc `ml-service`
commenté. Il suffit de le décommenter et de pointer le `build` vers ce dossier :

```yaml
  ml-service:
    build: ../moto-safety-ml   # chemin relatif depuis moto-safety-backend/
    container_name: moto-safety-ml
    restart: unless-stopped
    env_file:
      - ../moto-safety-ml/.env
    ports:
      - "8001:8001"
```

Aucune autre modification requise côté NestJS : `ml-client.service.ts`
appelle déjà `POST /scoring/predict` avec le bon payload, et ce service y
répond avec exactement le contrat attendu (`note_globale`, `niveau_risque`,
etc. — voir `app/routers/predict.py`). Testé en local avec le payload exact
envoyé par le client TypeScript (freinage/accélération/virage/excès de
vitesse détectés correctement).

En cas d'erreur réseau ou de timeout sur cet appel, le fallback heuristique
déjà présent côté worker NestJS (`heuristiques.service.ts`) prend le relais
automatiquement — et donnera le **même score** puisque les seuils sont
répliqués à l'identique dans `app/services/heuristics_compat.py`.

### Étape suivante suggérée

Décommenter le bloc `ml-service` dans `docker-compose.yml`, lancer
`docker compose up -d --build`, puis déclencher un trajet de test pour
vérifier dans les logs NestJS que `sourceCalcul: 'ml'` apparaît (au lieu de
`'heuristique'`) — signe que l'appel HTTP vers ce microservice fonctionne.

## Prochaines étapes suggérées

- Étendre `schemas.py` avec la détection de trajectoire anormale complète
  (actuellement seul le virage brusque point-à-point est couvert — une vraie
  détection d'itinéraire anormal demanderait de comparer au trajet habituel).
- Ajouter des tests unitaires sur `heuristics.py` (cas limites : points GPS
  identiques, vitesse manquante, trajet très court).
- Une fois assez de trajets réels collectés : suivre `training/README.md`.
