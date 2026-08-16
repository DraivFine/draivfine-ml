from __future__ import annotations

from collections import Counter

from app.config import Settings
from app.schemas import ScoringResponse, TrajetScoringRequest
from app.services import heuristics
from app.services.ml_model import MLScoringModel


def scorer_trajet(
    requete: TrajetScoringRequest, settings: Settings, ml_model: MLScoringModel
) -> ScoringResponse:
    points = requete.points
    evenements = heuristics.detecter_evenements(points, requete.contexte, settings)
    distance_km, duree_minutes = heuristics.calculer_distance_et_duree(points)

    score_ml = ml_model.predire_score(points)
    if score_ml is not None:
        score = score_ml
        methode = f"ml_model:{ml_model.version}"
    else:
        score = heuristics.calculer_score(evenements)
        methode = "heuristique"

    resume = dict(Counter(e.type.value for e in evenements))

    return ScoringResponse(
        trajet_id=requete.trajet_id,
        score=score,
        methode=methode,
        nb_points_analyses=len(points),
        distance_km=distance_km,
        duree_minutes=duree_minutes,
        evenements=evenements,
        resume=resume,
    )
