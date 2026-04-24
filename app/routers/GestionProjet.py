from fastapi import APIRouter, HTTPException,Depends, Response, status
from sqlalchemy.exc import IntegrityError
from .. import schemas,oauth2
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from typing import Annotated, List
from app import models
router = APIRouter(tags=["Projets"])
@router.post("/projets", status_code=status.HTTP_201_CREATED, response_model=schemas.ProjetResponse)
def create_projet(projet: schemas.ProjetsBase,db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
   try:
        new_projet = models.Projet(**projet.dict())
        db.add(new_projet)
        db.commit()
        db.refresh(new_projet)
        return new_projet

   except IntegrityError as e:
        db.rollback()

        # 🔥 CAS DUPLICATE NOM
        if "projet_nom_key" in str(e.orig):
            raise HTTPException(
                status_code=400,
                detail="❌ Ce nom de projet existe déjà. Veuillez choisir un autre nom."
            )

        # fallback autre erreur DB
        raise HTTPException(
            status_code=500,
            detail="Erreur base de données lors de la création du projet."
        )
 
@router.get("/projets", response_model=List[schemas.ProjetResponse])
def get_projets(db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]):
    projets = db.query(models.Projet).options(
        joinedload(models.Projet.salarie)
    ).all()
    
    return projets
@router.get("/projets/{id}", response_model=List[schemas.ProjetResponse])
def get_projet(id: int, db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]):
    projets = db.query(models.Projet).options(joinedload(models.Projet.salarie)).filter(models.Projet.salarie_id == id).all()
    
    return projets


@router.delete("/projet/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_projet(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    projet = db.query(models.Projet).filter(models.Projet.id == id).first()

    if not projet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Projet with id {id} not found"
        )

    has_historiques = db.query(models.HistoriqueSalarie).filter(
        models.HistoriqueSalarie.projet_id == id
    ).first()

    if has_historiques:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer : ce projet a des historiques"
        )

    db.delete(projet)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.put("/projet/{id}", response_model=schemas.ProjetResponse)
def update_projet(
    id: int,
    updated_projet: schemas.ProjetsBase,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    try:
        projet_query = db.query(models.Projet).filter(models.Projet.id == id)
        projet = projet_query.first()

        if not projet:
            raise HTTPException(
                status_code=404,
                detail=f"Projet with id {id} not found"
            )

        projet_query.update(updated_projet.dict(), synchronize_session=False)
        db.commit()

        return projet_query.first()

    except IntegrityError as e:
        db.rollback()

        if "projet_nom_key" in str(e.orig):
            raise HTTPException(
                status_code=400,
                detail="❌ Ce nom de projet existe déjà."
            )

        raise HTTPException(
            status_code=500,
            detail="Erreur base de données lors de la modification."
        )