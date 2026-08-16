"""
Endpoint appelé tel quel par src/scoring/ml-client.service.ts (NestJS) —
ne pas changer le path ni les noms de champs sans mettre à jour ce fichier
en parallèle.

Contrairement à /score (contrat plus riche, pensé pour d'autres consommateurs
futurs), cet endpoint n'exige pas de header d'authentification : le client
NestJS actuel n'en envoie pas. Le service n'est de toute façon jamais exposé
publiquement (réseau Docker interne uniquement, cf. docker-compose).
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import PredictResponse, TrajetPredictRequest
from app.services import heuristics_compat
from app.services.ml_model import MLScoringModel

router = APIRouter(prefix="/scoring", tags=["compat-nestjs"])


@router.post("/predict", response_model=PredictResponse)
async def predict(requete: TrajetPredictRequest, request: Request) -> PredictResponse:
    ml_model: MLScoringModel = request.app.state.ml_model

    # Le modèle ML entraîné n'existe pas encore (cf. training/README.md) :
    # tant que ce n'est pas le cas, on utilise systématiquement l'heuristique
    # ci-dessous, qui réplique celle déjà présente côté NestJS.
    if ml_model.est_disponible():
        # TODO une fois un modèle entraîné disponible : adapter la feature
        # extraction pour ce contrat (points en snake_case, un seul scalaire
        # `acceleration`) puis appeler ml_model.predire_score(...).
        pass

    return heuristics_compat.calculer(requete.trajet_id, requete.points)
