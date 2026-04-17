from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Annotated
from langdetect import detect

from groq import Groq
from ..database import get_db
from ..schemas import ChatRequest
from ..config import settings
from app import models

router = APIRouter(tags=["Chatbot"])

client = Groq(api_key=settings.chatbot_api_key)

system_prompt = """
Tu es Elzei AI Assistant.

RÈGLES :
- uniquement Elzei Consulting
- réponse dans la langue utilisateur
- ne jamais inventer
- utiliser uniquement les données fournies
"""


# ================= SMART FILTER =================
def build_context(db: Session, message: str):

    context = ""
    msg = message.lower()

    # 🔥 PROJETS (filtrage intelligent)
    projets = db.query(models.Projet).all()
    projets_filtered = [
        p for p in projets
        if p.nom and p.nom.lower() in msg
        or p.client and p.client.lower() in msg
    ]

    if not projets_filtered:
        projets_filtered = projets[:5]  # fallback

    context += "\nPROJETS:\n"
    for p in projets_filtered:
        context += f"- {p.nom} | client:{p.client} | marge:{p.marge_cible} | tjm:{p.tjm}\n"

    # 🔥 SALARIÉS
    salaries = db.query(models.Salaries).all()
    salaries_filtered = [
        s for s in salaries
        if s.username.lower() in msg
        or s.email.lower() in msg
    ]

    if not salaries_filtered:
        salaries_filtered = salaries[:5]

    context += "\nSALARIÉS:\n"
    for s in salaries_filtered:
        context += f"- {s.username} | tjm:{s.tjm} | role:{s.role.name if s.role else 'N/A'}\n"

    # 🔥 HISTORIQUE (très important KPI)
    historiques = db.query(models.HistoriqueSalarie).all()
    historiques_filtered = historiques[:10]

    context += "\nHISTORIQUE:\n"
    for h in historiques_filtered:
        context += (
            f"- {h.salarie.username if h.salarie else 'N/A'} "
            f"| projet:{h.projet_sal.nom if h.projet_sal else 'N/A'} "
            f"| jours:{h.joursTravailles} | rentabilité:{h.rentabilite}\n"
        )

    return context


# ================= ENDPOINT =================
@router.post("/chat")
def chat_elzei(
    req: ChatRequest,
    db: Annotated[Session, Depends(get_db)]
):

    user_message = req.message.strip()[:1000]
    lang = detect(user_message)

    context = build_context(db, user_message)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": system_prompt + f"\nLANG: {lang}\n{context}"
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    return {"response": response.choices[0].message.content}