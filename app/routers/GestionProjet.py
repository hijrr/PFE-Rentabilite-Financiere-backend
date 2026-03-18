from fastapi import APIRouter, HTTPException,Depends, Response, status
from .. import schemas,oauth2
from sqlalchemy.orm import Session
from ..database import get_db
from typing import List
from app import models
router = APIRouter(tags=["Projets"])
@router.post("/projets", status_code=status.HTTP_201_CREATED, response_model=schemas.ProjetResponse)
def create_projet(projet: schemas.ProjetsBase,db: Session = Depends(get_db),current_user: models.User = Depends(oauth2.get_current_user)
):
    new_projet = models.Projet(**projet.dict())
    db.add(new_projet)
    db.commit()
    db.refresh(new_projet)
    return new_projet
 
@router.get("/projets", response_model=List[schemas.ProjetResponse])
def get_projets(db: Session = Depends(get_db),current_user: models.User = Depends(oauth2.get_current_user),
):
    return db.query(models.Projet).all()


@router.delete("/projet/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_projet(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    salarie_query = db.query(models.Projet).filter(models.Projet.id == id)
    salarie = salarie_query.first()
    if not salarie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Projet with id {id} not found")
    salarie_query.delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.put("/projet/{id}", response_model=schemas.ProjetResponse)
def update_projet(
    id: int,
    updated_projet: schemas.ProjetsBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    salarie_query = db.query(models.Projet).filter(models.Projet.id == id)
    salarie = salarie_query.first()
    if not salarie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Projet with id {id} not found")
    salarie_query.update(updated_projet.dict(), synchronize_session=False)
    db.commit()
    return salarie_query.first()
