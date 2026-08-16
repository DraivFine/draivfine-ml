from fastapi import APIRouter, Request

from app.config import get_settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = get_settings()
    ml_model = getattr(request.app.state, "ml_model", None)
    return HealthResponse(
        status="ok",
        ml_model_charge=bool(ml_model and ml_model.est_disponible()),
        version=settings.VERSION,
    )
