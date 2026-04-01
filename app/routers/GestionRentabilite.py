
from fastapi import APIRouter, File, UploadFile
import pdfplumber
import json
import requests
import pandas as pd
import fitz  # PyMuPDF
router = APIRouter(tags=["Extraction de données"])
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:latest"
@router.post("/extract-ficheDePaie/")
async def extract_payroll(file: UploadFile = File(...)):

    # 1️⃣ Extraire texte du PDF
    with pdfplumber.open(file.file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    print("=== TEXTE EXTRAIT DU PDF ===")
    print(text)

    # 2️⃣ Prompt corrigé
    prompt = f"""
Tu es un expert en analyse de documents administratifs français. Ta mission est d'extraire des données spécifiques à partir du texte d'une fiche de paie et de les retourner EXCLUSIVEMENT au format JSON, sans aucune explication.
DESCRIPTION DES COLONNES (De gauche à droite) :
- Colonne 1 : Libellé/Élément de paie
- Colonne 2 : Base
- Colonne 3 : Taux
- Colonne 4 : Part Salariale (À déduire)
- Colonne 5 : Part Employeur (À payer / Net)
- Colonne 6 : Charges Patronales (Tout à droite)

INSTRUCTIONS DE NAVIGATION :
 **repas_restaurant** :
   - Localise la ligne contenant les mots "Repas" ou "restaurant".
   - Sur cette ligne, prends la valeur numérique située dans la colonne "A payer" (généralement l'avant-dernière ).
**total_cotisations_salariales** : valeur correspondant à la ligne "Total des cotisations et contributions" dans la 4eme  colonne "A déduire". 
 **net_avant_impot** : Cherche spécifiquement le libellé "Net à payer avant impôt sur le revenu" ou "Net fiscal".
 **salaire_brut** : valeur correspondant à la ligne "Salaire brut"  dans la colonne des montants "A déduire".  
**charges_patronales** : 
    Cherche la ligne qui contient exactement : "Total des cotisations et contributions"
    
    Sur cette ligne, il y a deux nombres qui se suivent :
    - Premier nombre = cotisations salariales
    - Deuxième nombre = charges patronales ← c'est celui-ci que je veux
    
    Les deux nombres sont séparés par un espace. tu vois Total des cotisations et contributions nb1 nb2 nb3
    
   tu dois prend nb2 et nb3 juste apres l'espace de nb1.
    
Regles de formatage :
1. Les valeurs financières doivent être des nombres (float), pas des chaînes.
2. Utilise le point (.) comme séparateur décimal.
3. Supprime les espaces dans les nombres (ex: "3 916.66" → 3916.66).
4. Ne fournis aucune explication avant ou après le JSON.
5. Ne mets pas de backticks Markdown.

RÈGLES STRICTES :
- Ne devine pas. Ne mets pas 0 par défaut.
- Si tu ne trouves vraiment pas, mets null.
- Retourne EXCLUSIVEMENT un objet JSON.

Texte source :
---
{text}
---

Extrais les informations suivantes dans cette structure exacte :
{{
  "salaire_brut": null,
  "total_cotisations_salariales": null,
  "charges_patronales": null,
  "repas_restaurant": null,
  "net_avant_impot": null,
  "net_paye": null
}}
"""

    # 3️⃣ Appel à Ollama
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "seed": 42
        }
    }

   
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)

    data = r.json()
    print("=== REPONSE BRUTE OLLAMA ===")
    print(data)

    # 4️⃣ Nettoyage JSON (supprimer backticks Markdown si présent)
    clean_text = data.get("response", "").strip()
    clean_text = clean_text.replace("```json", "")
    clean_text = clean_text.replace("```", "")
    clean_text = clean_text.strip()

    try:
        result = json.loads(clean_text)
        return result
    except Exception as e:
        return {
            "error": "Impossible de parser le JSON",
            "raw_response": clean_text
        }
        
@router.post("/extract-noteDeFrais/")
async def extract_payroll(file: UploadFile = File(...)):

    try:
        df = pd.read_excel(file.file)
    except Exception:
        return {"error": "Le fichier n'est pas un Excel valide"}
    text = df.to_string(index=False)
    # 2️⃣ Prompt corrigé
    prompt = f"""
Tu es un expert en extraction de données comptables. Ta mission est d'analyser cette synthèse de notes de frais et d'extraire le montant final dû.

Règles :
1. Extrais la valeur numérique correspondant au "Total à verser",ou au montant final de la synthèse de dernier ligne.
2. La valeur doit être un nombre (float), pas une chaîne.
3. Utilise le point (.) comme séparateur décimal.
4. Supprime les symboles monétaires (€) et les espaces.
5. Retourne EXCLUSIVEMENT le JSON, sans aucune explication ni backticks.

Texte source :
---
{text}
---

Structure JSON attendue :
{{
  "total_a_verser": null,
}}
"""

    # 3️⃣ Appel à Ollama
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "seed": 42
        }
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)

    data = r.json()
    print(data)

    # 4️⃣ Nettoyage JSON (supprimer backticks Markdown si présent)
    clean_text = data.get("response", "").strip()
    clean_text = clean_text.replace("```json", "")
    clean_text = clean_text.replace("```", "")
    clean_text = clean_text.strip()

    try:
        result = json.loads(clean_text)
        return result
    except Exception as e:
        return {
            "error": "Impossible de parser le JSON",
            "raw_response": clean_text
        }


@router.post("/extract-noteDeFraisKilometrique/")
async def extract_payroll(file: UploadFile = File(...)):

    try:
        df = pd.read_excel(file.file)
    except Exception:
        return {"error": "Le fichier n'est pas un Excel valide"}
    text = df.to_string(index=False)
    # 2️⃣ Prompt corrigé
    prompt = f"""
Tu es un expert en extraction de données comptables. Ton objectif est d'extraire le montant final de remboursement situé tout en bas à droite du tableau de frais kilométriques.

Instructions :
1. Repère la toute dernière ligne et la dernière colonne du tableau (souvent nommée "Total", "Total en euro" ou "Total net").
2. Extrais uniquement la valeur numérique finale.
3. Transforme la valeur en nombre (float) : remplace la virgule par un point, supprime les symboles (€) et les espaces.
4. Ne fournis aucune explication, raisonnement ou balise Markdown. 

Texte source (Tableau Excel converti) :
---
{text}
---

Structure JSON attendue :
{{
  "total_en_euro": null
}}
"""

    # 3️⃣ Appel à Ollama
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "seed": 42
        }
    }

    
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    data = r.json()
    print(data)

    # 4️⃣ Nettoyage JSON (supprimer backticks Markdown si présent)
    clean_text = data.get("response", "").strip()
    clean_text = clean_text.replace("```json", "")
    clean_text = clean_text.replace("```", "")
    clean_text = clean_text.strip()
    if not clean_text.endswith('}'):
        clean_text += '}'


    try:
        result = json.loads(clean_text)
        return result
    except Exception as e:
        return {
            "error": "Impossible de parser le JSON",
            "raw_response": clean_text
        }

@router.post("/extract-infosPersonnel/")
async def extract_infosPersonnel(file: UploadFile = File(...)):
    try:
        # 1️⃣ Lecture du contenu du PDF
        content = await file.read()
        text = ""

        # Ouverture du PDF en mémoire avec PyMuPDF
        with fitz.open(stream=content, filetype="pdf") as doc:
            for page in doc:
                blocks = page.get_text("blocks")
                for b in blocks:
                    text += b[4] + "\n"
        # 2️⃣ Prompt optimisé
        prompt = f"""
Tu es un automate d'extraction de données comptables. 
Analyse le texte suivant pour extraire les infos du SALARIÉ.

Règles strictes :
1. "nom_salarie" : Ligne commençant par Monsieur ou Madame.
2. "adresse" : Adresse complète du SALARIÉ (Rue, CP, Ville).
3. "numero_ss" : Cherche spécifiquement apres "Convention collective:" apres la premier valeur .

Texte source :
---
{text}
---

Format attendu :
{{
  "nom_salarie": null,
  "adresse": null,
  "numero_ss": null
}}
"""

        # 3️⃣ Appel à Ollama
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "seed": 42
            }
        }

        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        data = r.json()

        print(data)

        # 4️⃣ Nettoyage JSON
        clean_text = data.get("response", "").strip()
        clean_text = clean_text.replace("```json", "").replace("```", "").strip()

        # 🔥 sécuriser JSON
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1
        clean_text = clean_text[start:end]

        try:
            result = json.loads(clean_text)
            return result

        except Exception:
            return {
                "error": "Impossible de parser le JSON",
                "raw_response": clean_text
            }

    except Exception as e:
        return {
            "error": str(e)
        }