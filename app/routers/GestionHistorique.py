from fastapi import APIRouter, HTTPException,Depends, Response, status
from sqlalchemy.exc import IntegrityError
from .Notification import _broadcast,_analyse_un_projet,traiter_notifications
import asyncio
from .. import schemas,oauth2
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from typing import Annotated, List
from app import models
router = APIRouter(tags=["Historique"])

@router.post("/historique", status_code=status.HTTP_201_CREATED, response_model=schemas.HistoriqueSalarieResponse)
async def create_historique(
    historique: schemas.HistoriqueSalarieCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    new_historique = models.HistoriqueSalarie(**historique.dict())

    db.add(new_historique)
    db.commit()
    db.refresh(new_historique)

    projet = db.query(models.Projet).filter(
        models.Projet.id == new_historique.projet_id
    ).first()

    if projet:
        asyncio.create_task(traiter_notifications(projet.id))

    return new_historique


@router.get("/historiques", response_model=List[schemas.HistoriqueSalarieResponse])
def get_historiques(db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]):
   historiques = db.query(models.HistoriqueSalarie).options(
        joinedload(models.HistoriqueSalarie.salarie),joinedload(models.HistoriqueSalarie.projet_sal)
    ).all()
    
   return historiques

@router.put("/historique/{id}", response_model=schemas.HistoriqueSalarieResponse)
async def update_historique(
    id: int,
    updated_historique: schemas.HistoriqueSalarieCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    try:
        historique_query = db.query(models.HistoriqueSalarie).filter(
            models.HistoriqueSalarie.id == id
        )

        historique = historique_query.first()

        if not historique:
            raise HTTPException(status_code=404, detail="Historique not found")

        historique_query.update(updated_historique.dict(), synchronize_session=False)
        db.commit()

        projet = db.query(models.Projet).filter(
            models.Projet.id == historique.projet_id
        ).first()

        if projet:
            asyncio.create_task(traiter_notifications(projet.id))

        return historique_query.first()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Erreur base de données lors de la modification."
        )