from fastapi import APIRouter, HTTPException,Depends, Response, status
from .. import schemas,oauth2
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from typing import Annotated, List
from app import models
router = APIRouter(tags=["Historique"])

@router.post("/historique", status_code=status.HTTP_201_CREATED, response_model=schemas.HistoriqueSalarieResponse)
def create_historique(historique: schemas.HistoriqueSalarieCreate, db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]):
    new_historique = models.HistoriqueSalarie(**historique.dict())
    db.add(new_historique)
    db.commit()
    db.refresh(new_historique)
    return new_historique


@router.get("/historiques", response_model=List[schemas.HistoriqueSalarieResponse])
def get_historiques(db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]):
   historiques = db.query(models.HistoriqueSalarie).options(
        joinedload(models.HistoriqueSalarie.salarie),joinedload(models.HistoriqueSalarie.projet_sal)
    ).all()
    
   return historiques