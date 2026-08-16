from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "moto-safe-ml"
    VERSION: str = "0.1.0"

    # Sécurité: le service n'est PAS exposé publiquement, il n'est appelé
    # que par le backend NestJS via le réseau Docker interne.
    # On protège quand même par une clé partagée simple.
    INTERNAL_API_KEY: str = "X2Fn6oujcmCTeAnyXueF2938BSdsa0nW6lFWTSAa5J4"

    # Chemin vers un modèle entraîné (joblib). Si le fichier n'existe pas,
    # le service bascule automatiquement sur les heuristiques.
    ML_MODEL_PATH: str = "training/model.joblib"

    # Seuils heuristiques par défaut (MVP avant modèle ML)
    SEUIL_FREINAGE_BRUSQUE_MS2: float = 4.0       # décélération (m/s^2)
    SEUIL_ACCELERATION_BRUSQUE_MS2: float = 3.5   # accélération positive (m/s^2)
    SEUIL_VIRAGE_BRUSQUE_DEG_PAR_SEC: float = 25.0
    MARGE_EXCES_VITESSE_KMH: float = 10.0         # tolérance au-dessus de la limite

    class Config:
        env_file = ".env"
        env_prefix = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
