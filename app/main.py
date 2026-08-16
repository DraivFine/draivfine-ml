import logging

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health, predict, scoring
from app.services.ml_model import MLScoringModel

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Microservice interne de scoring comportemental pour MotoSafe. "
        "Appelé exclusivement par le backend NestJS (module scoring) via le réseau Docker interne."
    ),
)


@app.on_event("startup")
async def charger_modele() -> None:
    # Chargé une seule fois au démarrage, réutilisé pour toutes les requêtes.
    app.state.ml_model = MLScoringModel(settings)


app.include_router(health.router)
app.include_router(scoring.router)
app.include_router(predict.router)
