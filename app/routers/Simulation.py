from typing import Optional
import json
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sklearn.tree import DecisionTreeClassifier

from ..models import HistoriqueSalarie, Projet
from ..database import get_db
from .PredictionIA import (
    convert_numpy,
    entrainer_modele_probabiliste,
    predire_marges_probabiliste,
)
from groq import Groq
from ..config import settings

client_groq = Groq(api_key=settings.chatbot_api_key)
router = APIRouter(tags=["Simulation"])


# ─────────────────────────────
# SCHEMA
# ─────────────────────────────
class SimulationParams(BaseModel):
    tjm: Optional[float] = None
    jours_travailles: Optional[float] = None
    repas_restaurant: Optional[float] = None
    total_note_frais: Optional[float] = None
    total_note_kilometrique: Optional[float] = None


# ══════════════════════════════════════════════════════════
# 🌳 DECISION TREE SUR LE MOIS
# ══════════════════════════════════════════════════════════

def entrainer_decision_tree_mois(db: Session):
    projets = db.query(Projet).all()
    X, y = [], []

    for p in projets:
        rows = db.query(HistoriqueSalarie).filter(
            HistoriqueSalarie.projet_id == p.id
        ).all()

        for r in rows:
            tjm_r = float(r.tjm or 0)
            jours_r = float(r.joursTravailles or 0)
            paye_r = float(r.paye or 0)

            frais_r = (
                float(r.repasRestaurant or 0)
                + float(r.totalNoteFrais or 0)
                + float(r.totalNoteKilometrique or 0)
            )

            snhr_r = float(r.salaireNetHorsRepas or 0)
            rent_r = float(r.rentabilite or 0)

            X.append([tjm_r, jours_r, paye_r, frais_r, snhr_r])

            if rent_r > 500:
                y.append("BON_MOIS")
            elif rent_r < 0:
                y.append("MAUVAIS_MOIS")
            else:
                y.append("MOYEN_MOIS")

    if len(X) < 5:
        return None, None

    dt = DecisionTreeClassifier(max_depth=4, random_state=42)
    dt.fit(np.array(X), np.array(y))

    return dt, ["tjm", "jours", "paye", "frais_total", "snhr"]


# ══════════════════════════════════════════════════════════
# 🌳 CLASSIFICATION MOIS SIMULÉ
# ══════════════════════════════════════════════════════════

def classifier_mois_simule(
    db: Session,
    tjm: float,
    jours: float,
    repas: float,
    nf: float,
    nk: float,
    snhr_sim: float,
    net_payer: float,
):
    dt, features = entrainer_decision_tree_mois(db)

    frais_sim = repas + nf + nk
    facture_brute = tjm * jours

    # ✅ FORMULES CORRIGÉES (ALIGNÉ FRONT ANGULAR)

    net_avant_impot = net_payer
    net_hors_repas = net_avant_impot - repas
    total_percu = net_avant_impot + nf + nk

    cout_sim = total_percu

    rent_paye = facture_brute - total_percu
    rent_non_paye = 0 - total_percu

    def regle(rent):
        if rent > 500:
            return "BON_MOIS"
        if rent < 0:
            return "MAUVAIS_MOIS"
        return "MOYEN_MOIS"

    if dt is None:
        return {
            "cas_paye": {
                "classe": regle(rent_paye),
                "confiance": 1.0,
                "probas": {},
                "rentabilite": round(rent_paye, 2),
                "totaleFacture": round(facture_brute, 2),
            },
            "cas_non_paye": {
                "classe": regle(rent_non_paye),
                "confiance": 1.0,
                "probas": {},
                "rentabilite": round(rent_non_paye, 2),
                "totaleFacture": 0.0,
            },
            "facture_brute": round(facture_brute, 2),
            "cout_sim": round(cout_sim, 2),
            "impact_non_paye": round(rent_paye - rent_non_paye, 2),
        }

    X_paye = np.array([[tjm, jours, 1.0, frais_sim, snhr_sim]])
    X_npaye = np.array([[tjm, jours, 0.0, frais_sim, snhr_sim]])

    cls_p = dt.predict(X_paye)[0]
    prob_p = dt.predict_proba(X_paye)[0]

    cls_np = dt.predict(X_npaye)[0]
    prob_np = dt.predict_proba(X_npaye)[0]

    return {
        "cas_paye": {
            "classe": cls_p,
            "confiance": round(float(np.max(prob_p)), 3),
            "probas": {c: round(float(p), 3) for c, p in zip(dt.classes_, prob_p)},
            "rentabilite": round(rent_paye, 2),
            "totaleFacture": round(facture_brute, 2),
        },
        "cas_non_paye": {
            "classe": cls_np,
            "confiance": round(float(np.max(prob_np)), 3),
            "probas": {c: round(float(p), 3) for c, p in zip(dt.classes_, prob_np)},
            "rentabilite": round(rent_non_paye, 2),
            "totaleFacture": 0.0,
        },
        "facture_brute": round(facture_brute, 2),
        "cout_sim": round(cout_sim, 2),
        "impact_non_paye": round(rent_paye - rent_non_paye, 2),
    }


# ══════════════════════════════════════════════════════════
# 🤖 IA CONSEILS
# ══════════════════════════════════════════════════════════

def generer_conseils_simulation(prompt: str):
    try:
        chat = client_groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=500,
        )

        content = chat.choices[0].message.content

        try:
            cleaned = content.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "verdict": "neutre",
                "resume": content[:200] if content else "Analyse non disponible",
                "conseils": [],
                "conseil_tjm": None,
                "conseil_jours": None,
                "seuil_rentabilite": None,
            }

    except Exception:
        return {
            "verdict": "neutre",
            "resume": "Analyse indisponible.",
            "conseils": [],
            "conseil_tjm": None,
            "conseil_jours": None,
            "seuil_rentabilite": None,
        }


# ══════════════════════════════════════════════════════════
# 🚀 ENDPOINT PRINCIPAL
# ══════════════════════════════════════════════════════════

@router.post("/simulation/projet/{projet_id}")
def simuler_projet(
    projet_id: int,
    params: SimulationParams,
    db: Session = Depends(get_db)
):
    rows = db.query(HistoriqueSalarie).filter(
        HistoriqueSalarie.projet_id == projet_id
    ).order_by(HistoriqueSalarie.date).all()

    if not rows:
        raise HTTPException(404, "Aucune donnée")

    df = pd.DataFrame([{
        "date": r.date,
        "cout": float(r.totalePercu or 0),
        "facture": float(r.totaleFacture or 0),
        "rentabilite": float(r.rentabilite or 0),
    } for r in rows])

    df["date"] = pd.to_datetime(df["date"])
    df["mois_index"] = np.arange(len(df))
    df["paye"] = (df["facture"] > 0).astype(int)

    last = rows[-1]
    paye_last = 1 if (last.totaleFacture or 0) > 0 else 0

    last_reel = {
        "tjm": float(last.tjm or 0),
        "jours": float(last.joursTravailles or 0),
        "repas": float(last.repasRestaurant or 0),
        "note_frais": float(last.totalNoteFrais or 0),
        "note_kilo": float(last.totalNoteKilometrique or 0),
        "net_payer": float(last.netPayer or 0),
        "facture": float(last.totaleFacture or 0),
        "cout": float(last.totalePercu or 0),
        "rentabilite": float(last.rentabilite or 0),
    }

    tjm = params.tjm or last_reel["tjm"]
    jours = params.jours_travailles or last_reel["jours"]
    repas = params.repas_restaurant or last_reel["repas"]
    nf = params.total_note_frais or last_reel["note_frais"]
    nk = params.total_note_kilometrique or last_reel["note_kilo"]

    facture_brute = tjm * jours
    facture_sim = facture_brute * paye_last

    net_avant_impot = last_reel["net_payer"]
    net_hors_repas = net_avant_impot - repas
    total_percu = net_avant_impot + nf + nk

    cout_sim = total_percu
    rent_sim = facture_sim - total_percu

    idx = len(df) - 1
    df.loc[idx, "facture"] = facture_sim
    df.loc[idx, "cout"] = cout_sim
    df.loc[idx, "rentabilite"] = rent_sim
    df.loc[idx, "paye"] = 1 if facture_sim > 0 else 0

    model_lr, scaler, metriques = entrainer_modele_probabiliste(df)
    predictions = predire_marges_probabiliste(model_lr, scaler, df, 3)

    profil_dt = classifier_mois_simule(
        db=db,
        tjm=tjm,
        jours=jours,
        repas=repas,
        nf=nf,
        nk=nk,
        snhr_sim=net_hors_repas,
        net_payer=net_avant_impot,
    )

    prompt = f"""
Tu es un expert en finance. Réponds UNIQUEMENT en JSON valide :
{{
  "verdict": "positif"|"négatif"|"neutre",
  "resume": "résumé court max 20 mots",
  "conseils": [{{"type":"action|alerte|optimisation","titre":"max 6 mots","detail":"max 40 mots","priorite":"haute|moyenne|faible"}}],
  "conseil_tjm": "conseil TJM ou null",
  "conseil_jours": "conseil jours ou null",
  "seuil_rentabilite": "seuil ou null"
}}

Situation réelle : TJM={last_reel['tjm']}€, jours={last_reel['jours']}, rentabilité={last_reel['rentabilite']:.0f}€
Simulation       : TJM={tjm}€, jours={jours}, coût={cout_sim:.0f}€
Si PAYÉ          : facture={profil_dt['cas_paye']['totaleFacture']:.0f}€, rentabilité={profil_dt['cas_paye']['rentabilite']:.0f}€, DT → {profil_dt['cas_paye']['classe']}
Si NON PAYÉ      : rentabilité={profil_dt['cas_non_paye']['rentabilite']:.0f}€, DT → {profil_dt['cas_non_paye']['classe']}
Perte si non payé: {profil_dt['impact_non_paye']:.0f}€
Prévisions 3 mois: {[f"{p['mois']}→{p['marge_probable']:.0f}€" for p in predictions]}
"""

    conseils_ia = generer_conseils_simulation(prompt)

    return convert_numpy({
        "last_reel": last_reel,
        "simulation": {
            "facture_brute": round(facture_brute, 2),
            "facture_sim": round(facture_sim, 2),
            "cout": round(cout_sim, 2),
            "net_hors_repas": round(net_hors_repas, 2),
            "rentabilite": round(rent_sim, 2),
        },
        "profil_dt": profil_dt,
        "predictions": predictions,
        "metriques": metriques,
        "conseils_ia": conseils_ia,
    })