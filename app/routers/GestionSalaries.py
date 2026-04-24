from fastapi import APIRouter, HTTPException,Depends, Response, status
from sqlalchemy.exc import IntegrityError
from .. import schemas,oauth2
from sqlalchemy.orm import Session
from ..database import get_db
from typing import Annotated, List
from app import models
router = APIRouter(tags=["Salaries"])

@router.post("/salaries", status_code=status.HTTP_201_CREATED, response_model=schemas.SalariesResponse)
def create_post(salarie: schemas.SalariesBase,db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    try:
        new_salarie = models.Salaries(**salarie.dict())
        db.add(new_salarie)
        db.commit()
        db.refresh(new_salarie)
        return new_salarie

    except IntegrityError as e:
        db.rollback()

        error_str = str(e.orig).lower()

        # 🔥 username duplicate
        if "username" in error_str:
            raise HTTPException(
                status_code=400,
                detail="❌ Ce nom d'utilisateur existe déjà."
            )

        # 🔥 email duplicate
        if "email" in error_str:
            raise HTTPException(
                status_code=400,
                detail="❌ Cet email existe déjà."
            )

        raise HTTPException(
            status_code=500,
            detail="Erreur base de données lors de la création du salarié."
        )
 
@router.get("/salaries", response_model=List[schemas.SalariesResponse])
def get_salaries(db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)],
):
    return db.query(models.Salaries).all()
 
@router.delete("/salarie/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_salarie(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    salarie = db.query(models.Salaries).filter(models.Salaries.id == id).first()

    if not salarie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salarie with id {id} not found"
        )

    has_projets = db.query(models.Projet).filter(models.Projet.salarie_id == id).first()
    if has_projets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer : ce salarié a des projets"
        )

    has_historiques = db.query(models.HistoriqueSalarie).filter(models.HistoriqueSalarie.salarie_id == id).first()
    if has_historiques:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer : ce salarié a des historiques"
        )

    db.delete(salarie)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.put("/salarie/{id}", response_model=schemas.SalariesResponse)
def update_salarie(
    id: int,
    updated_salarie: schemas.SalariesBase,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    try:
        salarie_query = db.query(models.Salaries).filter(models.Salaries.id == id)
        salarie = salarie_query.first()

        if not salarie:
            raise HTTPException(
                status_code=404,
                detail=f"Salarie with id {id} not found"
            )

        salarie_query.update(updated_salarie.dict(), synchronize_session=False)
        db.commit()

        return salarie_query.first()

    except IntegrityError as e:
        db.rollback()

        error_str = str(e.orig).lower()

        if "username" in error_str:
            raise HTTPException(
                status_code=400,
                detail="❌ Ce nom d'utilisateur existe déjà."
            )

        if "email" in error_str:
            raise HTTPException(
                status_code=400,
                detail="❌ Cet email existe déjà."
            )

        raise HTTPException(
            status_code=500,
            detail="Erreur base de données lors de la modification."
        )