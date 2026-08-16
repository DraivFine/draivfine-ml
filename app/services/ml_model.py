"""
Chargement optionnel d'un modèle entraîné (scikit-learn ou XGBoost, sérialisé
avec joblib). Tant qu'aucun modèle n'a été entraîné et déposé à ML_MODEL_PATH,
`est_disponible()` retourne False et le service scoring.py bascule sur les
heuristiques (app/services/heuristics.py).

Voir training/README.md pour le pipeline d'entraînement prévu.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from app.config import Settings
from app.schemas import PointCapteur

logger = logging.getLogger(__name__)


class MLScoringModel:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = None
        self._version = "non-charge"
        self._tenter_chargement()

    def _tenter_chargement(self) -> None:
        path = self._settings.ML_MODEL_PATH
        if not os.path.exists(path):
            logger.info("Aucun modèle ML trouvé à %s — heuristiques utilisées.", path)
            return
        try:
            import joblib  # import local: dépendance optionnelle tant qu'il n'y a pas de modèle

            self._model = joblib.load(path)
            self._version = os.path.basename(path)
            logger.info("Modèle ML chargé depuis %s", path)
        except Exception:  # noqa: BLE001 - on ne veut jamais planter le service pour ça
            logger.exception("Échec du chargement du modèle ML, fallback heuristiques.")
            self._model = None

    def est_disponible(self) -> bool:
        return self._model is not None

    @property
    def version(self) -> str:
        return self._version

    def predire_score(self, points: List[PointCapteur]) -> Optional[float]:
        """Retourne un score [0, 100] ou None si le modèle n'est pas disponible.

        NOTE: la feature extraction ici doit rester alignée avec celle utilisée
        à l'entraînement (voir training/features.py une fois créé).
        """
        if not self.est_disponible():
            return None

        features = self._extraire_features(points)
        prediction = self._model.predict([features])[0]
        return round(float(max(min(prediction, 100.0), 0.0)), 1)

    @staticmethod
    def _extraire_features(points: List[PointCapteur]) -> List[float]:
        vitesses = [p.vitesse_kmh for p in points if p.vitesse_kmh is not None]
        vitesse_moy = sum(vitesses) / len(vitesses) if vitesses else 0.0
        vitesse_max = max(vitesses) if vitesses else 0.0
        return [
            float(len(points)),
            vitesse_moy,
            vitesse_max,
        ]
