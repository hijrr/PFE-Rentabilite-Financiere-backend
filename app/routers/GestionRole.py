from fastapi import APIRouter, HTTPException,Depends, Response, status
from sqlalchemy.exc import DBAPIError, IntegrityError
from .. import schemas,oauth2
from sqlalchemy.orm import Session
from ..database import get_db
from typing import Annotated, List
from app import models
router = APIRouter(tags=["Role"])

@router.post("/role", status_code=status.HTTP_201_CREATED, response_model=schemas.RoleResponse)
def create_post(role: schemas.RoleBase,db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    try:
        new_role = models.Role(**role.dict())
        db.add(new_role)
        db.commit()
        db.refresh(new_role)
        return new_role

    except IntegrityError as e:
        db.rollback()

        error_str = str(e.orig).lower()

        # 🔥 duplicate role name
        if "role" in error_str or "name" in error_str:
            raise HTTPException(
                status_code=400,
                detail="❌ Ce nom de rôle existe déjà."
            )

        raise HTTPException(
            status_code=500,
            detail="Erreur base de données lors de la création du rôle."
        )
 
@router.get("/roles", response_model=List[schemas.RoleResponse])
def get_salaries(db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)],
):
    return db.query(models.Role).all()
 
@router.delete("/role/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    role_query = db.query(models.Role).filter(models.Role.id == id)
    role = role_query.first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rôle avec l'id {id} non trouvé."
        )

    try:
        role_query.delete(synchronize_session=False)
        db.commit()
    except DBAPIError as e:
        db.rollback()
        # Vérifier si c'est une violation de clé étrangère
        if hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23503':  # code FK violation Postgres
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de supprimer ce rôle : il est utilisé par des salariés existants."
            )
        # Autres erreurs
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur interne est survenue lors de la suppression."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
 
@router.put("/role/{id}", response_model=schemas.RoleResponse)
def update_salarie(
    id: int,
    updated_salarie: schemas.RoleBase,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    try:
        role_query = db.query(models.Role).filter(models.Role.id == id)
        role = role_query.first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Salarie with id {id} not found")
        role_query.update(updated_salarie.dict(), synchronize_session=False)
        db.commit()
        return role_query.first()
    except IntegrityError as e:
        db.rollback()
        error_str = str(e.orig).lower()
        # 🔥 duplicate role name
        if "role" in error_str or "name" in error_str:
            raise HTTPException(
                status_code=400,
                detail="❌ Ce nom de rôle existe déjà."
            )
        raise HTTPException(
            status_code=500,
            detail="Erreur base de données lors de la modification du rôle."
        )