from typing_extensions import Annotated
from sqlalchemy.orm import Session
from .. import schemas,oauth2
from fastapi import APIRouter, HTTPException,Depends
from ..database import get_db
from fastapi import APIRouter, HTTPException, Query
from app import models
import requests
DOLIBARR_BASE_URL = "https://alwafa-conseil.com/dolibarr/api/index.php"
DOLIBARR_API_KEY = "SGnvc5cCGFJD9sp29giVt816E4INf94m"
LOGO_BASE_URL = "https://alwafa-conseil.com/htdocs/custom/logo_directory/"

router = APIRouter(tags=["Clients"])
@router.get("/client-logo/{modulepart}/{file_path:path}", responses={  500: {"description": "Erreur interne lors de la récupération du logo",  "content": {     "application/json": {
 "example": {"detail": "Erreur lors de l'appel à Dolibarr"}  }}, }})
def get_client_logo(modulepart: str, file_path: str,):

    url = f"{DOLIBARR_BASE_URL}/documents/download"

    headers = {
        "DOLAPIKEY": DOLIBARR_API_KEY
    }

    params = {
        "modulepart": modulepart,
        "original_file": file_path,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()

        data = resp.json()

        return {
            "filename": data.get("filename"),
            "content_type": data.get("content-type"),
            "base64": data.get("content")  # Dolibarr renvoie le base64 ici
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/clients", responses={ 500: { "description": "Erreur lors de la récupération des clients", }})
def get_clients(limit: Annotated[int, Query()]=10000):
    url = f"{DOLIBARR_BASE_URL}/thirdparties?limit={limit}"
    headers = {"DOLAPIKEY": DOLIBARR_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Lève une erreur si le statut != 200
        data = response.json()
        return {"clients": data}  
    except requests.exceptions.RequestException as e:
         raise HTTPException(status_code=500, detail=str(e))
    
    
@router.get("/invoices",responses={500: {"description": "Erreur lors de la récupération des factures",}})
def get_invoices(limit: Annotated[int, Query()]=10000):
    url = f"{DOLIBARR_BASE_URL}/invoices?limit={limit}"
    headers = {"DOLAPIKEY": DOLIBARR_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Lève une erreur si le statut != 200
        data = response.json()
        return {"invoices": data}  
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    

@router.get("/clientsBD", responses={500: {"description": "Erreur lors de la récupération des clients"}})
def populate_clients(
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)],
    limit: Annotated[int, Query()] = 10000
):
    try:
        url = f"{DOLIBARR_BASE_URL}/thirdparties?limit={limit}"
        headers = {"DOLAPIKEY": DOLIBARR_API_KEY}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        clients = resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur de communication avec Dolibarr : {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du parsing des données Dolibarr : {str(e)}")

    # Récupérer tous les IDs clients déjà présents (entiers)
    existing_ids = {row[0] for row in db.query(models.Client.id).all()}
    new_count = 0

    for c in clients:
        cid = c.get("id")
        if cid is None:
            continue
        try:
            cid_int = int(cid)          
        except (ValueError, TypeError):
            continue                    
        if cid_int in existing_ids:
            continue                    

        try:
            client = models.Client(
                id=cid_int,
                name=c.get("name"),
                code_client=c.get("code_client"),
                client=str(c.get("client")) if c.get("client") is not None else None,
                logo=c.get("logo"),
                email=c.get("email"),
                phone=c.get("phone"),
                fax=c.get("fax"),
                url=c.get("url"),
                address=c.get("address"),
                zip=c.get("zip"),
                town=c.get("town"),
                country_code=c.get("country_code"),
                idprof1=c.get("idprof1"),
                idprof2=c.get("idprof2"),
                idprof3=c.get("idprof3"),
                tva_intra=c.get("tva_intra"),
                forme_juridique=c.get("forme_juridique"),
                capital=float(c["capital"]) if c.get("capital") else None,
                effectif=int(c["effectif"]) if c.get("effectif") else None,
                date_creation=c.get("date_creation"),
                date_modification=c.get("date_modification")
            )
            db.add(client)
            new_count += 1
        except Exception as e:
            # Log de l'erreur et continuation
            print(f"Erreur sur client {cid_int}: {e}")
            continue

    db.commit()
    return {"status": "success", "count": new_count}

@router.get("/facturesBD", responses={500: {"description": "Erreur lors de la récupération des factures"}})
def populate_factures(
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)],
    limit: Annotated[int, Query()] = 10000
):
    try:
        url = f"{DOLIBARR_BASE_URL}/invoices?limit={limit}"
        headers = {"DOLAPIKEY": DOLIBARR_API_KEY}

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        factures = resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur de communication avec Dolibarr : {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du parsing des données Dolibarr : {str(e)}")

    # Récupérer tous les IDs déjà présents en base
    existing_ids = {row[0] for row in db.query(models.Facture.id).all()}
    new_count = 0

    for f in factures:
        fid = f.get("id")
        if fid is None:
            continue
        try:
            fid_int = int(fid)         
        except (ValueError, TypeError):
            continue
        if fid_int in existing_ids:
            continue
        try:
            facture = models.Facture(
                id=int(fid),
                ref=f.get("ref") or f"REF-{fid}",
                socid=int(f["socid"]) if f.get("socid") else 0,
                date=int(f["date"]) if f.get("date") else None,
                date_lim_reglement=int(f["date_lim_reglement"]) if f.get("date_lim_reglement") else None,
                date_creation=int(f["date_creation"]) if f.get("date_creation") else None,
                date_validation=int(f["date_validation"]) if f.get("date_validation") else None,
                total_ht = float(f["total_ht"]) if f.get("total_ht") is not None else 0.0,
                total_tva=float(f["total_tva"]) if f.get("total_tva") is not None else 0.0,
                total_ttc=float(f["total_ttc"]) if f.get("total_ttc") is not None else 0.0,
                sumpayed=float(f["sumpayed"]) if f.get("sumpayed") is not None else 0.0,
                tjm=float(f["lines"][0]["subprice"]) if f.get("lines") and len(f["lines"]) > 0 and f["lines"][0].get("subprice") else None,
                jours_travailles=float(f["lines"][0]["qty"]) if f.get("lines") and len(f["lines"]) > 0 and f["lines"][0].get("qty") else None,
                resteapayer=float(f["resteapayer"]) if f.get("resteapayer") is not None else 0.0,
                paye=str(f.get("paye", "0")),
                statut=str(f.get("statut", "0")),
                online_payment_url=f.get("online_payment_url")
            )
            db.add(facture)
            new_count += 1
        except Exception as e:
            # Log l'erreur mais continue avec les autres factures
            print(f"Erreur sur facture {fid}: {e}")
            continue

    db.commit()
    return {"status": "success", "count": new_count}

from concurrent.futures import ThreadPoolExecutor

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
            future_clients = executor.submit(sync_clients)
            future_factures = executor.submit(sync_factures)

            clients_result = future_clients.result()
            factures_result = future_factures.result()

        return {
            "clients": clients_result,
            "invoices": factures_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/GETClients",)
def get_projets(db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]):
    clients= db.query(models.Client).all()
    return {"clients": clients}
    
@router.get("/GETFactures",)
def get_factures(db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(oauth2.get_current_user)]):
    factures= db.query(models.Facture).all()
    return {"invoices": factures}