"""
Scoring heuristique basé sur des seuils physiques simples.
Objectif MVP : détecter freinage brusque, accélération brusque,
virage brusque et excès de vitesse à partir d'une série de points capteurs.

Ce module ne dépend d'aucun modèle entraîné : il sert de fallback
et de baseline pour comparer les futurs modèles ML.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from app.config import Settings
from app.schemas import (
    ContexteTrajet,
    Evenement,
    PointCapteur,
    TypeEvenement,
)

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _acceleration_longitudinale(p1: PointCapteur, p2: PointCapteur) -> float:
    """Approxime l'accélération longitudinale (m/s^2) à partir de la norme du vecteur accéléro.

    On soustrait ~9.81 (gravité) pour ne garder que l'accélération liée au mouvement.
    C'est volontairement simple : un vrai pipeline ferait une fusion capteur
    (orientation du device, filtre de Kalman, etc.) — hors scope MVP.
    """
    norme = math.sqrt(p2.accel_x**2 + p2.accel_y**2 + p2.accel_z**2)
    return abs(norme - 9.81)


def _delta_secondes(p1: PointCapteur, p2: PointCapteur) -> float:
    return max((p2.timestamp - p1.timestamp).total_seconds(), 0.001)


def _vitesse_variation_kmh_par_sec(p1: PointCapteur, p2: PointCapteur) -> float:
    if p1.vitesse_kmh is None or p2.vitesse_kmh is None:
        return 0.0
    dt = _delta_secondes(p1, p2)
    return (p2.vitesse_kmh - p1.vitesse_kmh) / dt


def _variation_cap_deg_par_sec(p1: PointCapteur, p2: PointCapteur) -> float:
    if p1.cap is None or p2.cap is None:
        return 0.0
    dt = _delta_secondes(p1, p2)
    diff = abs(p2.cap - p1.cap)
    diff = min(diff, 360 - diff)  # plus court chemin angulaire
    return diff / dt


def detecter_evenements(
    points: List[PointCapteur],
    contexte: ContexteTrajet,
    settings: Settings,
) -> List[Evenement]:
    evenements: List[Evenement] = []
    limite = contexte.limite_vitesse_kmh or 60.0

    for p1, p2 in zip(points, points[1:]):
        # --- Freinage / accélération brusque (via accéléro) ---
        accel_ms2 = _acceleration_longitudinale(p1, p2)
        variation_vitesse = _vitesse_variation_kmh_par_sec(p1, p2)

        if variation_vitesse < 0 and accel_ms2 >= settings.SEUIL_FREINAGE_BRUSQUE_MS2:
            evenements.append(
                Evenement(
                    type=TypeEvenement.FREINAGE_BRUSQUE,
                    timestamp=p2.timestamp,
                    latitude=p2.latitude,
                    longitude=p2.longitude,
                    severite=_severite(accel_ms2, settings.SEUIL_FREINAGE_BRUSQUE_MS2, cap=10.0),
                    valeur_mesuree=round(accel_ms2, 2),
                    seuil=settings.SEUIL_FREINAGE_BRUSQUE_MS2,
                )
            )
        elif variation_vitesse > 0 and accel_ms2 >= settings.SEUIL_ACCELERATION_BRUSQUE_MS2:
            evenements.append(
                Evenement(
                    type=TypeEvenement.ACCELERATION_BRUSQUE,
                    timestamp=p2.timestamp,
                    latitude=p2.latitude,
                    longitude=p2.longitude,
                    severite=_severite(accel_ms2, settings.SEUIL_ACCELERATION_BRUSQUE_MS2, cap=8.0),
                    valeur_mesuree=round(accel_ms2, 2),
                    seuil=settings.SEUIL_ACCELERATION_BRUSQUE_MS2,
                )
            )

        # --- Excès de vitesse ---
        if p2.vitesse_kmh is not None and p2.vitesse_kmh > limite + settings.MARGE_EXCES_VITESSE_KMH:
            evenements.append(
                Evenement(
                    type=TypeEvenement.EXCES_VITESSE,
                    timestamp=p2.timestamp,
                    latitude=p2.latitude,
                    longitude=p2.longitude,
                    severite=_severite(p2.vitesse_kmh, limite, cap=limite * 1.5),
                    valeur_mesuree=p2.vitesse_kmh,
                    seuil=limite,
                )
            )

        # --- Virage / trajectoire anormale ---
        variation_cap = _variation_cap_deg_par_sec(p1, p2)
        if variation_cap >= settings.SEUIL_VIRAGE_BRUSQUE_DEG_PAR_SEC:
            evenements.append(
                Evenement(
                    type=TypeEvenement.VIRAGE_BRUSQUE,
                    timestamp=p2.timestamp,
                    latitude=p2.latitude,
                    longitude=p2.longitude,
                    severite=_severite(
                        variation_cap, settings.SEUIL_VIRAGE_BRUSQUE_DEG_PAR_SEC, cap=90.0
                    ),
                    valeur_mesuree=round(variation_cap, 1),
                    seuil=settings.SEUIL_VIRAGE_BRUSQUE_DEG_PAR_SEC,
                )
            )

    return evenements


def _severite(valeur: float, seuil: float, cap: float) -> float:
    """Normalise un dépassement de seuil en score de sévérité [0, 1]."""
    if valeur <= seuil:
        return 0.0
    ratio = (valeur - seuil) / max(cap - seuil, 0.001)
    return round(min(max(ratio, 0.0), 1.0), 2)


# Poids appliqués au score global par type d'événement (points retirés sur 100,
# pondérés par la sévérité individuelle de chaque occurrence).
POIDS_EVENEMENT = {
    TypeEvenement.FREINAGE_BRUSQUE: 6.0,
    TypeEvenement.ACCELERATION_BRUSQUE: 4.0,
    TypeEvenement.EXCES_VITESSE: 8.0,
    TypeEvenement.VIRAGE_BRUSQUE: 5.0,
    TypeEvenement.TRAJECTOIRE_ANORMALE: 5.0,
}


def calculer_score(evenements: List[Evenement]) -> float:
    score = 100.0
    for e in evenements:
        poids = POIDS_EVENEMENT.get(e.type, 5.0)
        score -= poids * (0.4 + 0.6 * e.severite)  # même un événement léger coûte un minimum
    return round(max(score, 0.0), 1)


def calculer_distance_et_duree(points: List[PointCapteur]) -> Tuple[float, float]:
    distance_km = 0.0
    for p1, p2 in zip(points, points[1:]):
        distance_km += _haversine_km(p1.latitude, p1.longitude, p2.latitude, p2.longitude)
    duree_minutes = (points[-1].timestamp - points[0].timestamp).total_seconds() / 60.0
    return round(distance_km, 3), round(duree_minutes, 2)
