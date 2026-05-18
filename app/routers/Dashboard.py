from sqlalchemy import desc, func
from fastapi import APIRouter, HTTPException,Depends
from app.database import get_db
from app.models import Client, Facture, Salaries,Projet,HistoriqueSalarie
from sqlalchemy.orm import Session
router = APIRouter(tags=["KPI"])

@router.get("/salaries/tjm")
def tjm_salaries(db: Session = Depends(get_db)):
    result = db.query(Salaries.username, Salaries.tjm).all()
    return [{"salarie": r[0], "tjm": r[1]} for r in result]

@router.get("/clients/top_ca")
def top_clients(db: Session = Depends(get_db)):
    result = db.query(
        Client.name,
        func.sum(Facture.total_ttc).label("ca")
    ).join(Facture, Facture.socid == Client.id
    ).group_by(Client.name
    ).order_by(desc("ca")).limit(10).all()
    
    return [{"client": r[0], "ca": r[1]} for r in result]

@router.get("/kpi/marge_moyenne")
def marge_moyenne(db: Session = Depends(get_db)):
    marge = db.query(func.avg(Projet.marge_cible)).scalar()
    return {"marge_moyenne": marge or 0}

@router.get("/kpi/evolution_ca")
def evolution_ca(db: Session = Depends(get_db), annee: int = None):
    query = db.query(
        func.to_char(func.to_timestamp(Facture.date_creation), 'YYYY-MM').label("mois"),
        func.sum(Facture.total_ttc).label("ca")
    )
    if annee:
        query = query.filter(func.to_char(func.to_timestamp(Facture.date_creation), 'YYYY') == str(annee))
    query = query.group_by("mois").order_by("mois")
    result = query.all()
    return [{"mois": r[0], "ca": float(r[1])} for r in result]


@router.get("/kpi/rentabilite_salaries")
def rentabilite_salaries(db: Session = Depends(get_db)):
    result = db.query(
        Salaries.username,
        func.sum(HistoriqueSalarie.rentabilite).label("total")
    ).join(HistoriqueSalarie
    ).group_by(Salaries.username
    ).order_by(desc("total")).limit(3).all()

    return [{"nom": r[0], "rentabilite": r[1]} for r in result]

@router.get("/kpi/top_projets")
def top_projets(db: Session = Depends(get_db)):
    result = db.query(
        Projet.nom,
        func.sum(HistoriqueSalarie.rentabilite).label("total")
    ).join(HistoriqueSalarie
    ).group_by(Projet.nom
    ).order_by(desc("total")).limit(3).all()

    return [{"nom": r[0], "rentabilite_totale": r[1]} for r in result]

@router.get("/kpi/global")
def global_kpi(db: Session = Depends(get_db)):
    total_operations = db.query(func.count(HistoriqueSalarie.id)).scalar()
    rentabilite_total = db.query(func.sum(HistoriqueSalarie.rentabilite)).scalar()
    avg_tjm = db.query(func.avg(Salaries.tjm)).scalar()

    return {
        "total_operations": total_operations or 0,
        "rentabilite_total": rentabilite_total or 0,
        "avg_tjm": avg_tjm or 0
    }
@router.get("/dashboard/factures/impayees")
def dashboard_factures_impayees(db: Session = Depends(get_db), limit: int = 10):
    result = db.query(
        Facture.id,
        Facture.ref,
        Facture.total_ttc,
        Facture.sumpayed,
        Facture.resteapayer,
        Facture.date_lim_reglement,
        Client.name
    ).join(Client, Facture.socid == Client.id
    ).filter(Facture.paye != "1"
    ).order_by(desc(Facture.resteapayer)
    ).limit(limit).all()

    return [
        {
            "id": r[0],
            "reference": r[1],
            "total_ttc": float(r[2] or 0),
            "montant_paye": float(r[3] or 0),
            "reste_a_payer": float(r[4] or 0),
            "date_lim_reglement": r[5],
            "client": r[6]
        }
        for r in result
    ]

@router.get("/dashboard/projets/statut-paiement")
def dashboard_projets_statut_paiement(db: Session = Depends(get_db)):
    result = db.query(
        Projet.status_paiement,
        func.count(Projet.id).label("nombre")
    ).group_by(Projet.status_paiement).all()

    return [
        {
            "status_paiement": r[0] or "non_renseigne",
            "nombre": r[1]
        }
        for r in result
    ]
