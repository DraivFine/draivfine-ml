"""
Schémas Pydantic partagés par les routers et les services.
Le contrat ici DOIT rester synchro avec ce qu'envoie le worker BullMQ
côté NestJS (module scoring -> ml.client.ts).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TypeEvenement(str, Enum):
    FREINAGE_BRUSQUE = "freinage_brusque"
    ACCELERATION_BRUSQUE = "acceleration_brusque"
    EXCES_VITESSE = "exces_vitesse"
    TRAJECTOIRE_ANORMALE = "trajectoire_anormale"
    VIRAGE_BRUSQUE = "virage_brusque"


class PointCapteur(BaseModel):
    """Un point de mesure brut (accéléro + GPS), tel qu'ingéré par le module capteurs."""

    timestamp: datetime
    accel_x: float
    accel_y: float
    accel_z: float
    latitude: float
    longitude: float
    vitesse_kmh: Optional[float] = Field(
        default=None, description="Vitesse instantanée si dispo côté device (GPS-derived sinon)"
    )
    cap: Optional[float] = Field(
        default=None, ge=0, le=360, description="Cap/heading en degrés, si dispo"
    )

    @field_validator("vitesse_kmh")
    @classmethod
    def vitesse_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("vitesse_kmh ne peut pas être négative")
        return v


class ContexteTrajet(BaseModel):
    """Métadonnées optionnelles utiles à l'analyse (zone, type de route, etc.)."""

    limite_vitesse_kmh: Optional[float] = Field(
        default=60.0, description="Limite applicable au trajet/zone, défaut zone urbaine CM"
    )
    zone_urbaine: bool = True


class TrajetScoringRequest(BaseModel):
    trajet_id: str
    conducteur_id: Optional[str] = None
    contexte: ContexteTrajet = Field(default_factory=ContexteTrajet)
    points: List[PointCapteur]

    @field_validator("points")
    @classmethod
    def points_suffisants(cls, v: List[PointCapteur]) -> List[PointCapteur]:
        if len(v) < 2:
            raise ValueError("Au moins 2 points capteurs sont nécessaires pour scorer un trajet")
        return v


class Evenement(BaseModel):
    type: TypeEvenement
    timestamp: datetime
    latitude: float
    longitude: float
    severite: float = Field(ge=0, le=1, description="0 = mineur, 1 = critique")
    valeur_mesuree: float
    seuil: float
    details: Optional[str] = None


class ScoringResponse(BaseModel):
    trajet_id: str
    score: float = Field(ge=0, le=100, description="Score global du trajet, 100 = conduite exemplaire")
    methode: str = Field(description="'heuristique' ou 'ml_model:<version>'")
    nb_points_analyses: int
    distance_km: Optional[float] = None
    duree_minutes: Optional[float] = None
    evenements: List[Evenement]
    resume: dict = Field(
        default_factory=dict,
        description="Compteurs agrégés par type d'événement, pour affichage rapide côté NestJS",
    )


class HealthResponse(BaseModel):
    status: str
    ml_model_charge: bool
    version: str


# ---------------------------------------------------------------------------
# Contrat de compatibilité avec le backend NestJS déjà écrit
# (src/scoring/ml-client.service.ts). NE PAS renommer ces champs sans mettre
# à jour le client TypeScript en parallèle — le payload/la réponse ci-dessous
# DOIVENT rester en snake_case et matcher exactement ce que le client envoie
# et attend.
# ---------------------------------------------------------------------------


class PointCapteurCompat(BaseModel):
    horodatage: datetime
    latitude: float
    longitude: float
    vitesse: Optional[float] = None
    acceleration: Optional[float] = None
    gyroscope_x: Optional[float] = None
    gyroscope_y: Optional[float] = None
    gyroscope_z: Optional[float] = None


class TrajetPredictRequest(BaseModel):
    trajet_id: str
    points: List[PointCapteurCompat]

    @field_validator("points")
    @classmethod
    def points_suffisants(cls, v: List[PointCapteurCompat]) -> List[PointCapteurCompat]:
        if len(v) < 1:
            raise ValueError("Au moins 1 point capteur est nécessaire")
        return v


class NiveauRisque(str, Enum):
    FAIBLE = "FAIBLE"
    MODERE = "MODERE"
    ELEVE = "ELEVE"
    CRITIQUE = "CRITIQUE"


class PredictResponse(BaseModel):
    note_globale: float = Field(ge=0, le=100)
    niveau_risque: NiveauRisque
    freinages_brusques: int
    accelerations_brusques: int
    exces_vitesse: int
    trajectoire_anormale: bool
