from typing_extensions import Annotated
from sqlalchemy.orm import Session
from fastapi import APIRouter, HTTPException, Depends, Query
from ..database import get_db
from .. import oauth2
from app import models
import requests
from ..config import settings
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(tags=["Clients"])

dolibarr_config = {
    "url": settings.dolibarr_url,
    "api_key": settings.dolibarr_api_key
}

def get_headers():
    return {"DOLAPIKEY": dolibarr_config["api_key"]}


@router.post("/config/dolibarr")
def save_config(config: dict):
    dolibarr_config["url"] = config.get("url")
    print("URL mise à jour :", dolibarr_config["url"])
    dolibarr_config["api_key"] = config.get("apiKey")
    return {"message": "Configuration enregistrée"}

@router.get("/config/dolibarr")
def get_config():
    return dolibarr_config


@router.get("/client-logo/{modulepart}/{file_path:path}")
def get_client_logo(modulepart: str, file_path: str):

    url = f"{dolibarr_config['url']}/documents/download"

    params = {
        "modulepart": modulepart,
        "original_file": file_path,
    }

    try:
        resp = requests.get(url, headers=get_headers(), params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        return {
            "filename": data.get("filename"),
            "content_type": data.get("content-type"),
            "base64": data.get("content")
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# 📥 FETCH API DOLIBARR
# ================================

@router.get("/clients")
def get_clients(limit: Annotated[int, Query()] = 10000):
    url = f"{dolibarr_config['url']}/thirdparties?limit={limit}"

    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        return {"clients": response.json()}
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invoices")
def get_invoices(limit: Annotated[int, Query()] = 10000):
    url = f"{dolibarr_config['url']}/invoices?limit={limit}"

    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        return {"invoices": response.json()}
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# 📦 SYNC CLIENTS → DB
# ================================

def populate_clients(db: Session, current_user, limit=10000):

    url = f"{dolibarr_config['url']}/thirdparties?limit={limit}"

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        resp.raise_for_status()
        clients = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    existing_ids = {row[0] for row in db.query(models.Client.id).all()}
    new_count = 0

    for c in clients:
        try:
            cid = int(c.get("id"))
            if cid in existing_ids:
                continue

            client = models.Client(
                id=cid,
                name=c.get("name"),
                code_client=c.get("code_client"),
                email=c.get("email"),
                phone=c.get("phone"),
                address=c.get("address"),
                town=c.get("town"),
                country_code=c.get("country_code")
            )

            db.add(client)
            new_count += 1

        except Exception:
            continue

    db.commit()
    return {"status": "success", "count": new_count}


def populate_factures(db: Session, current_user, limit=10000):

    url = f"{dolibarr_config['url']}/invoices?limit={limit}"

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        resp.raise_for_status()
        factures = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    existing_ids = {row[0] for row in db.query(models.Facture.id).all()}
    new_count = 0

    for f in factures:
        try:
            fid = int(f.get("id"))
            if fid in existing_ids:
                continue

            facture = models.Facture(
                id=fid,
                ref=f.get("ref"),
                total_ttc=float(f.get("total_ttc", 0))
            )

            db.add(facture)
            new_count += 1

        except Exception:
            continue

    db.commit()
    return {"status": "success", "count": new_count}



@router.get("/syncAll")
def sync_all(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)],
):

    def sync_clients():
        return populate_clients(db, current_user)

    def sync_factures():
        return populate_factures(db, current_user)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            clients_result = executor.submit(sync_clients).result()
            factures_result = executor.submit(sync_factures).result()

        return {
            "clients": clients_result,
            "invoices": factures_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# 📊 DATA FROM DB
# ================================

@router.get("/GETClients")
def get_clients_db(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    return {"clients": db.query(models.Client).all()}


@router.get("/GETFactures")
def get_factures_db(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(oauth2.get_current_user)]
):
    return {"invoices": db.query(models.Facture).all()}


@router.delete("/reset-db")
def reset_db(db: Session = Depends(get_db)):
    db.query(models.Facture).delete()
    db.query(models.Client).delete()
    db.commit()
    return {"message": "Base de données vidée"}