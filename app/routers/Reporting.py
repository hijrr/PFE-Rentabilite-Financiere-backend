from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from datetime import datetime
from sqlalchemy import func

from app import models, oauth2
from ..database import get_db

router = APIRouter(tags=["Reporting"])

@router.get("/dashboard-mensuel-complet")
def dashboard_mensuel_complet(
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)],
    db: Session = Depends(get_db)
):

    today = datetime.now()
    mois_str = today.strftime("%Y-%m")  # "2026-04"

    # 👤 SALARIÉS
    salaries = db.query(models.Salaries).filter(
        models.Salaries.created_at >= datetime(today.year, today.month, 1)
    ).all()

    # 📁 PROJETS
    projets = db.query(models.Projet).filter(
        models.Projet.created_at >= datetime(today.year, today.month, 1)
    ).all()

    # 📊 HISTORIQUE (FIX IMPORTANT)
    historiques = db.query(models.HistoriqueSalarie).filter(
        models.HistoriqueSalarie.date.like(f"{mois_str}%")
    ).all()

    # 💰 AGRÉGATS (FIX IMPORTANT)
    agg = db.query(
        func.sum(models.HistoriqueSalarie.totaleFacture),
        func.sum(models.HistoriqueSalarie.totalePercu),
        func.sum(models.HistoriqueSalarie.salaireBrut),
        func.sum(models.HistoriqueSalarie.joursTravailles)
    ).filter(
        models.HistoriqueSalarie.date.like(f"{mois_str}%")
    ).first()

    total_facture = agg[0] or 0
    total_percu   = agg[1] or 0
    total_cout    = agg[2] or 0
    total_jours   = agg[3] or 0

    marge = total_facture - total_cout

    return {
        "mois": mois_str,

        # 👤 salariés
        "nb_salaries_ajoutes": len(salaries),
        "salaries": [
            {
                "nom": s.username,
                "email": s.email,
                "tjm": s.tjm
            } for s in salaries
        ],

        # 📁 projets
        "nb_projets_crees": len(projets),
        "projets": [
            {
                "nom": p.nom,
                "client": p.client,
                "tjm": p.tjm
            } for p in projets
        ],

        # 📊 historique
        "nb_activites": len(historiques),

        # 💰 KPI
        "total_facture": round(total_facture, 2),
        "total_percu": round(total_percu, 2),
        "total_cout": round(total_cout, 2),
        "marge": round(marge, 2),
        "jours_travailles": total_jours
    }