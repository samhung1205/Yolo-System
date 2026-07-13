"""Authenticated deterministic report downloads."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.agents.tools.report_tools import generate_detection_report_markdown_tool
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.report_export_service import render_markdown_pdf

router = APIRouter()


def _report_payload_or_error(
    db: Session,
    *,
    current_user: User,
    detection_id: int,
) -> dict:
    payload = generate_detection_report_markdown_tool(
        db,
        current_user=current_user,
        detection_id=detection_id,
    )
    if payload.get("ok"):
        return payload
    message = str(payload.get("error") or "Unable to generate report")
    if "not allowed" in message:
        code = status.HTTP_403_FORBIDDEN
    elif "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(status_code=code, detail=message)


@router.get("/detections/{detection_id}")
def download_detection_report(
    detection_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    format: Literal["markdown", "pdf"] = Query(default="pdf"),
) -> Response:
    payload = _report_payload_or_error(
        db,
        current_user=current_user,
        detection_id=detection_id,
    )
    markdown = payload["markdown"]
    stem = f"yolo-detection-{detection_id}-report"
    if format == "markdown":
        return Response(
            content=markdown.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{stem}.md"'},
        )

    pdf = render_markdown_pdf(markdown, detection_id=detection_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
    )
