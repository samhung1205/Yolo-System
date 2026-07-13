"""API for approved YOLO inference checkpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.integrations.model_registry import list_yolo_models
from app.models.user import User
from app.schemas.detection import YoloModelRead

router = APIRouter()


@router.get("", response_model=list[YoloModelRead])
def list_registered_yolo_models(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[YoloModelRead]:
    return [YoloModelRead(**spec.public_metadata()) for spec in list_yolo_models()]
