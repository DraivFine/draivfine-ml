"""
Réplique volontairement la logique de src/scoring/heuristiques.service.ts
(NestJS) — mêmes seuils, même formule de pénalités — pour que le score
heuristique soit identique, que le fallback se déclenche côté NestJS
(service ML injoignable) ou que le calcul soit fait ici.

Un point important : la version NestJS d'origine calcule le changement de
cap à partir de latitude/longitude mais avec une formule qui donne toujours
0 (bug de copier-coller : capA et capB utilisent les mêmes points). Ici on
utilise plutôt le gyroscope_z (vitesse angulaire) réellement remonté par le
capteur, ce qui est le signal correct pour détecter un virage brusque.
Si vous corrigez le bug côté NestJS plus tard, gardez les deux implémentations
alignées.
"""

from __future__ import annotations

import math
from typing import List

from app.schemas import NiveauRisque, PointCapteurCompat, PredictResponse

SEUILS_HEURISTIQUES = {
    "freinage_brusque_ms2": -3.5,   # décélération (m/s²), acceleration signée
    "acceleration_brusque_ms2": 3.0,
    "exces_vitesse_kmh": 80.0,
    "ecart_trajectoire_degres": 45.0,  # changement de cap cumulé entre deux points
}

# Hypothèse : gyroscope_z en rad/s (convention la plus courante pour les
# capteurs mobiles react-native-sensors/expo-sensors). Si le mobile envoie
# du deg/s, retirer la conversion ci-dessous.
_RAD_TO_DEG = 180.0 / math.pi


def _deriver_niveau_risque(note: float) -> NiveauRisque:
    if note >= 80:
        return NiveauRisque.FAIBLE
    if note >= 60:
        return NiveauRisque.MODERE
    if note >= 35:
        return NiveauRisque.ELEVE
    return NiveauRisque.CRITIQUE


def calculer(trajet_id: str, points: List[PointCapteurCompat]) -> PredictResponse:
    freinages_brusques = 0
    accelerations_brusques = 0
    exces_vitesse = 0
    trajectoire_anormale = False

    for i, p in enumerate(points):
        if p.acceleration is not None:
            if p.acceleration <= SEUILS_HEURISTIQUES["freinage_brusque_ms2"]:
                freinages_brusques += 1
            if p.acceleration >= SEUILS_HEURISTIQUES["acceleration_brusque_ms2"]:
                accelerations_brusques += 1

        if p.vitesse is not None and p.vitesse >= SEUILS_HEURISTIQUES["exces_vitesse_kmh"]:
            exces_vitesse += 1

        if i > 0 and p.gyroscope_z is not None:
            dt = max((p.horodatage - points[i - 1].horodatage).total_seconds(), 0.001)
            changement_cap_deg = abs(p.gyroscope_z) * _RAD_TO_DEG * dt
            if changement_cap_deg >= SEUILS_HEURISTIQUES["ecart_trajectoire_degres"]:
                trajectoire_anormale = True

    penalites = (
        freinages_brusques * 4
        + accelerations_brusques * 3
        + exces_vitesse * 5
        + (10 if trajectoire_anormale else 0)
    )
    note_globale = max(0.0, min(100.0, 100.0 - penalites))

    return PredictResponse(
        note_globale=round(note_globale, 1),
        niveau_risque=_deriver_niveau_risque(note_globale),
        freinages_brusques=freinages_brusques,
        accelerations_brusques=accelerations_brusques,
        exces_vitesse=exces_vitesse,
        trajectoire_anormale=trajectoire_anormale,
    )
