import math
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def _round(value: float | int | None, digits: int = 2) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0.0
    return round(float(value), digits)


def _month_bounds(year: int | None = None, month: int | None = None) -> tuple[datetime, datetime, str]:
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end, f"{year:04d}-{month:02d}"


def build_monthly_dashboard(db: Session, year: int | None = None, month: int | None = None) -> dict[str, Any]:

    start, end, mois_str = _month_bounds(year, month)
    hist_filter = models.HistoriqueSalarie.date.like(f"{mois_str}%")

    # ── ACTIVITÉ RÉCENTE ─────────────────────────────────────────────────────────
    projects_created = db.query(func.count(models.Projet.id)).filter(
        models.Projet.created_at >= start,
        models.Projet.created_at < end,
    ).scalar() or 0

    salaries_created = db.query(func.count(models.Salaries.id)).filter(
        models.Salaries.created_at >= start,
        models.Salaries.created_at < end,
    ).scalar() or 0

    # ── TOTAUX GLOBAUX ───────────────────────────────────────────────────────────
    total_projects = db.query(func.count(models.Projet.id)).scalar() or 0
    total_salaries = db.query(func.count(models.Salaries.id)).scalar() or 0

    # ── FINANCES DU MOIS ─────────────────────────────────────────────────────────
    financial = db.query(
        func.coalesce(func.sum(models.HistoriqueSalarie.totaleFacture), 0),
        func.coalesce(func.sum(models.HistoriqueSalarie.totalePercu), 0),
    ).filter(hist_filter).first()

    total_facture = _round(financial[0])
    total_cout    = _round(financial[1])
    marge_estimee = _round(total_facture - total_cout)

    # ── TOP PROJET DU MOIS ───────────────────────────────────────────────────────
    # Classé par SUM(rentabilite) DESC — meilleure rentabilité nette du mois.
    # Retourne None si aucune ligne n'existe pour ce mois.
    top_projet_row = (
        db.query(
            models.HistoriqueSalarie.projet_id,
            func.sum(models.HistoriqueSalarie.rentabilite).label("rentabilite"),
            func.sum(models.HistoriqueSalarie.totaleFacture).label("facture"),
            func.sum(models.HistoriqueSalarie.totalePercu).label("cout"),
        )
        .filter(hist_filter)
        .group_by(models.HistoriqueSalarie.projet_id)
        .order_by(func.sum(models.HistoriqueSalarie.rentabilite).desc())
        .first()
    )

    top_projet = None
    if top_projet_row is not None:
        projet = db.query(models.Projet).filter(
            models.Projet.id == top_projet_row.projet_id
        ).first()

        top_projet = {
            "projet_id":   top_projet_row.projet_id,
            "nom":         projet.nom    if projet else f"Projet #{top_projet_row.projet_id}",
            "client":      projet.client.name if projet and projet.client else "", 
            "rentabilite": _round(top_projet_row.rentabilite),
            "facture":     _round(top_projet_row.facture),
            "cout":        _round(top_projet_row.cout),
            "marge":       _round((top_projet_row.facture or 0) - (top_projet_row.cout or 0)),
        }

    # ── RÉPONSE FINALE ───────────────────────────────────────────────────────────
    return {
        "mois":            mois_str,
        "date_generation": datetime.now().isoformat(),

        "activite_recente": {
            "projets_crees_ce_mois":    int(projects_created),
            "salaries_ajoutes_ce_mois": int(salaries_created),
        },

        "totaux_globaux": {
            "nombre_total_projets":  int(total_projects),
            "nombre_total_salaries": int(total_salaries),
        },

        "finances_mois": {
            "revenu_total":  total_facture,
            "cout_total":    total_cout,
            "marge_estimee": marge_estimee,
        },

        # None si aucun historique ce mois, sinon projet avec rentabilité max
        "top_projet": top_projet,
    }