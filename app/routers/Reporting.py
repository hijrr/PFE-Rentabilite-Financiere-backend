from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query

from app import models, oauth2
from app.services.reporting_service import build_monthly_dashboard
from ..database import get_db

router = APIRouter(tags=["Reporting"])

@router.get("/dashboard-mensuel-complet")
def dashboard_mensuel_complet(
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)],
    db: Session = Depends(get_db),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
):
    return build_monthly_dashboard(db, year=year, month=month)
