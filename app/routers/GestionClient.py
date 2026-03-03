from fastapi import APIRouter, FastAPI, HTTPException
import requests,os
import base64
DOLIBARR_BASE_URL = "https://alwafa-conseil.com/dolibarr/api/index.php"
DOLIBARR_API_KEY = "SGnvc5cCGFJD9sp29giVt816E4INf94m"
LOGO_BASE_URL = "https://alwafa-conseil.com/htdocs/custom/logo_directory/"

router = APIRouter(tags=["Clients"])
@router.get("/client-logo/{modulepart}/{file_path:path}")
def get_client_logo(modulepart: str, file_path: str):

    url = f"{DOLIBARR_BASE_URL}/documents/download"

    headers = {
        "DOLAPIKEY": DOLIBARR_API_KEY
    }

    params = {
        "modulepart": modulepart,
        "original_file": file_path
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
@router.get("/clients")
def get_clients():
    url = f"{DOLIBARR_BASE_URL}/thirdparties"
    headers = {"DOLAPIKEY": DOLIBARR_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Lève une erreur si le statut != 200
        data = response.json()
        return {"clients": data}  
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}