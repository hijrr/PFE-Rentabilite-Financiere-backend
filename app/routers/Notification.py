import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import Projet, Notification

from .PredictionIA import (
    get_donnees_projet,
    entrainer_modele_probabiliste,
    predire_marges_probabiliste,
    analyser_courbe_globale,
    generer_analyse_courbe_groq,
)
from app import models

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)

# ─────────────────────────────────────────────
# 🔹 WebSocket clients
# ─────────────────────────────────────────────
_ws_clients: list[WebSocket] = []

async def _broadcast(notification: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(notification, default=str))
        except Exception:
            dead.append(ws)

    for ws in dead:
        _ws_clients.remove(ws)


# ─────────────────────────────────────────────
# 🔹 WebSocket endpoint
# ─────────────────────────────────────────────
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)

    try:
        while True:
            await websocket.receive_text()  # keepalive
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ─────────────────────────────────────────────
# 🔹 Helpers DB
# ─────────────────────────────────────────────
def save_notification(db: Session, notif: dict):
    obj = Notification(**notif)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ─────────────────────────────────────────────
# 🔹 Analyse projet
# ─────────────────────────────────────────────
def _analyse_un_projet(db: Session, projet) -> list[dict]:

    notifications = []

    df = get_donnees_projet(db, projet.id)
    print("PROJET:", projet.nom)
    print("DATA:", df.shape)
    if df.empty or len(df) < 2:
        return []

    model_lr, scaler_lr, metriques = entrainer_modele_probabiliste(df)
    preds = predire_marges_probabiliste(model_lr, scaler_lr, df, n_mois=3)

    evolution = [
        {
            "mois": p["mois"],
            "marge": p["marge_probable"],
            "cout": p.get("cout", 0)
        }
        for p in preds
    ]

    analyse = analyser_courbe_globale(evolution, metriques, 3)

    # ── Alerte marge négative
    mois_negatifs = [p for p in preds if p["alerte"]]

    if mois_negatifs:
        notif = {
            "id": str(uuid.uuid4()),
            "type": "alerte",
            "niveau": "danger",
            "titre": f"Marge négative — {projet.nom}",
            "message": "Marge négative détectée",
            "recommandation": None,
            "projet_id": projet.id,
            "projet_nom": projet.nom,
            "lu": False,
            "date": datetime.utcnow(),
            "data": {"predictions": preds, "metriques": metriques},
        }
        notifications.append(notif)

    # ── Recommandation IA
    if analyse and abs(analyse.get("variation_pct", 0)) > 5:
        try:
            texte_ia = generer_analyse_courbe_groq(evolution, analyse, metriques, 3)

            notif = {
                "id": str(uuid.uuid4()),
                "type": "recommandation",
                "niveau": "warning",
                "titre": f"Recommandation IA — {projet.nom}",
                "message": f"Tendance {analyse.get('tendance')}",
                "recommandation": texte_ia,
                "projet_id": projet.id,
                "projet_nom": projet.nom,
                "lu": False,
                "date": datetime.utcnow(),
                "data": analyse,
            }

            notifications.append(notif)

        except Exception:
            pass

    return notifications


# ─────────────────────────────────────────────
# 🔹 Run check (DB + WS)
# ─────────────────────────────────────────────
async def _run_check(db: Session):

    projets = db.query(Projet).all()
    nouvelles = []
    notifications_a_envoyer = []

    # ── Analyse
    for projet in projets:
        try:
            nouvelles.extend(_analyse_un_projet(db, projet))
        except Exception as e:
            print("Erreur projet:", e)

    # ── Filtrer + préparer insert
    for notif in nouvelles:

        if not notification_existe(db, notif):

            obj = Notification(**notif)
            db.add(obj)
            notifications_a_envoyer.append(notif)

    # ── Commit une seule fois
    db.commit()

    # ── Broadcast async (non bloquant)
    for notif in notifications_a_envoyer:
        asyncio.create_task(_broadcast(notif))

    return len(notifications_a_envoyer)

def notification_existe(db: Session, notif: dict) -> bool:
    limite = datetime.utcnow() - timedelta(minutes=30)

    return db.query(models.Notification).filter(
        models.Notification.projet_id == notif["projet_id"],
        models.Notification.type == notif["type"],
        models.Notification.message == notif["message"],
        models.Notification.date >= limite
    ).first() is not None

async def traiter_notifications(projet_id: int):
    db = SessionLocal()

    try:
        projet = db.query(models.Projet).filter(
            models.Projet.id == projet_id
        ).first()

        if not projet:
            return

        notifications = _analyse_un_projet(db, projet)

        for notif in notifications:

            if not notification_existe(db, notif):

                obj = models.Notification(**notif)
                db.add(obj)
                db.commit()
                db.refresh(obj)

                await _broadcast(notif)

    finally:
        db.close()
# ─────────────────────────────────────────────
# 🔹 API REST
# ─────────────────────────────────────────────

@router.post("/check")
async def check_now(db: Session = Depends(get_db)):
    count = await _run_check(db)

    items = db.query(Notification).order_by(Notification.date.desc()).all()

    return {
        "message": f"{count} notifications générées",
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "niveau": n.niveau,
                "titre": n.titre,
                "message": n.message,
                "recommandation": n.recommandation,
                "projet_id": n.projet_id,
                "projet_nom": n.projet_nom,
                "lu": n.lu,
                "date": n.date.isoformat()
            }
            for n in items
        ]
    }

@router.get("")
def get_notifications(db: Session = Depends(get_db)):

    items = db.query(Notification).order_by(Notification.date.desc()).all()

    return {
        "total": len(items),
        "non_lues": sum(1 for n in items if not n.lu),
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "niveau": n.niveau,
                "titre": n.titre,
                "message": n.message,
                "recommandation": n.recommandation,
                "projet_id": n.projet_id,
                "projet_nom": n.projet_nom,
                "lu": n.lu,
                "date": n.date.isoformat()
            }
            for n in items
        ]
    }


@router.patch("/{notif_id}/read")
def mark_read(notif_id: str, db: Session = Depends(get_db)):

    notif = db.query(Notification).filter(Notification.id == notif_id).first()

    if notif:
        notif.lu = True
        db.commit()
        return {"ok": True}

    return {"ok": False}


@router.delete("/clear")
def clear_read(db: Session = Depends(get_db)):

    deleted = db.query(Notification).filter(Notification.lu == True).delete()
    db.commit()

    return {"deleted": deleted}


# ─────────────────────────────────────────────
# 🔹 Background polling
# ─────────────────────────────────────────────
async def _background_poller():

    while True:
        await asyncio.sleep(300)

        from ..database import SessionLocal
        db = SessionLocal()

        try:
            await _run_check(db)
        finally:
            db.close()