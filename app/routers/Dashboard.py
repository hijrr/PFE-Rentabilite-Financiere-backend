from sqlalchemy import desc, func
from fastapi import APIRouter, HTTPException,Depends
from app.database import get_db
from app.models import Client, Facture, Salaries
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