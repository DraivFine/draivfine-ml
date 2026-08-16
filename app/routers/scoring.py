from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.schemas import ScoringResponse, TrajetScoringRequest
from app.services.ml_model import MLScoringModel
from app.services.scorer import scorer_trajet

router = APIRouter(prefix="/score", tags=["scoring"])

# Le modèle est chargé une seule fois au démarrage du process (voir main.py),
# on le récupère via l'état de l'app plutôt que de le recharger à chaque requête.


def verifier_cle_interne(
    x_internal_api_key: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API interne invalide",
        )


@router.post(
    "",
    response_model=ScoringResponse,
    dependencies=[Depends(verifier_cle_interne)],
    summary="Score un trajet à partir d'une série de points capteurs",
)
async def scorer(
    requete: TrajetScoringRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ScoringResponse:
    ml_model: MLScoringModel = request.app.state.ml_model
    return scorer_trajet(requete, settings, ml_model)
