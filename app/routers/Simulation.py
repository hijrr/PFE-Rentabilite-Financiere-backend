from typing import Optional
import json
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sklearn.tree import DecisionTreeClassifier, export_text
from collections import Counter

from ..models import HistoriqueSalarie, Projet
from ..database import get_db
from .PredictionIA import (
    analyser_courbe_globale,
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


# ─────────────────────────────
# 🌳 LABEL RISQUE — correction variation_pct
# ─────────────────────────────
def calculer_label_risque(rent_moy, taux_paiement, nb_neg, total, variation):
    pct_neg = nb_neg / max(total, 1)

    if rent_moy > 500 and taux_paiement >= 0.8 and pct_neg < 0.1:
        return "RENTABLE"
    if rent_moy < 0 or pct_neg > 0.4:
        return "EN_DANGER"
    return "FRAGILE"


# ─────────────────────────────
# 🌳 TRAIN — correction variation_pct
# ─────────────────────────────
def entrainer_decision_tree(db: Session):
    projets = db.query(Projet).all()
    X, y = [], []

    for p in projets:
        rows = db.query(HistoriqueSalarie).filter(
            HistoriqueSalarie.projet_id == p.id
        ).all()
        if len(rows) < 3:
            continue

        rent = [float(r.rentabilite or 0) for r in rows]
        fact = [float(r.totaleFacture or 0) for r in rows]
        taux = sum(1 for f in fact if f > 0) / len(fact)
        nb_neg = sum(1 for r in rent if r < 0)
        rent_moy = float(np.mean(rent))

        # ✅ variation_pct correctement calculée
        variation = ((rent[-1] - rent[0]) / (abs(rent[0]) + 1e-6)) * 100

        X.append([rent_moy, nb_neg, taux, len(rows)])
        y.append(calculer_label_risque(rent_moy, taux, nb_neg, len(rows), variation))

    if len(X) < 3:
        return None, None, []

    dt = DecisionTreeClassifier(max_depth=4, random_state=42)
    dt.fit(np.array(X), np.array(y))
    return dt, ["rent_moy", "nb_neg", "taux_pay", "volume"], y


# ─────────────────────────────
# 🌳 CLASSIFICATION
# ─────────────────────────────
def classifier_profil_projet(db: Session, df_sim: pd.DataFrame):
    dt, features, labels = entrainer_decision_tree(db)

    if dt is None:
        return {"classe": "INCONNU", "confiance": 0.0}

    rent = df_sim["rentabilite"].tolist()
    fact = df_sim["facture"].tolist()

    X_pred = np.array([[
        np.mean(rent),
        sum(1 for r in rent if r < 0),
        sum(1 for f in fact if f > 0) / len(fact),
        len(df_sim),
    ]])

    classe = dt.predict(X_pred)[0]
    probas = dt.predict_proba(X_pred)[0]

    return {
        "classe": classe,
        "confiance": float(np.max(probas)),
        "probas": dict(zip(dt.classes_, probas))
    }


# ─────────────────────────────
# 🤖 IA CONSEILS
# ─────────────────────────────
def generer_conseils_simulation(prompt: str):
    try:
        chat = client_groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=500,
        )
        content = chat.choices[0].message.content

        # Tenter d'extraire un JSON (si l'IA a bien retourné du JSON)
        try:
            # Nettoyer les éventuels blocs markdown
            cleaned = content.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Si ce n'est pas du JSON, on retourne une structure par défaut avec le texte brut
            return {
                "verdict": "neutre",
                "resume": content[:200] if content else "Analyse non disponible",
                "conseils": [],
                "conseil_tjm": None,
                "conseil_jours": None,
                "seuil_rentabilite": None
            }
    except Exception as e:
        return {
            "verdict": "neutre",
            "resume": "Analyse indisponible pour le moment.",
            "conseils": [],
            "conseil_tjm": None,
            "conseil_jours": None,
            "seuil_rentabilite": None
        }

# ─────────────────────────────
# 🚀 ENDPOINT PRINCIPAL
# ─────────────────────────────
@router.post("/simulation/projet/{projet_id}")
def simuler_projet(projet_id: int, params: SimulationParams, db: Session = Depends(get_db)):

    rows = db.query(HistoriqueSalarie).filter(
        HistoriqueSalarie.projet_id == projet_id
    ).order_by(HistoriqueSalarie.date).all()
    if not rows:
        raise HTTPException(404, "Aucune donnée")

    df = pd.DataFrame([{
        "date": r.date, "cout": float(r.totalePercu or 0),
        "facture": float(r.totaleFacture or 0), "rentabilite": float(r.rentabilite or 0),
    } for r in rows])
    df["date"]       = pd.to_datetime(df["date"])
    df["mois_index"] = np.arange(len(df))
    df["paye"]       = (df["facture"] > 0).astype(int)

    last = rows[-1]

    # ✅ last_reel pour la comparaison frontend
    last_reel = {
        "tjm":        float(last.tjm or 0),
        "jours":      float(last.joursTravailles or 0),
        "facture":    float(last.totaleFacture or 0),
        "cout":       float(last.totalePercu or 0),
        "rentabilite":float(last.rentabilite or 0),
    }

    tjm   = params.tjm            if params.tjm            is not None else last_reel["tjm"]
    jours = params.jours_travailles if params.jours_travailles is not None else last_reel["jours"]
    repas = params.repas_restaurant if params.repas_restaurant is not None else float(last.repasRestaurant or 0)
    nf    = params.total_note_frais if params.total_note_frais is not None else float(last.totalNoteFrais or 0)
    nk    = params.total_note_kilometrique if params.total_note_kilometrique is not None else float(last.totalNoteKilometrique or 0)

    # ✅ paye_last pour cohérence
    paye_last   = 1 if (last.totaleFacture or 0) > 0 else 0
    facture_sim = tjm * jours * paye_last
    cout_sim    = float(last.salaireNetHorsRepas or 0) + repas + nf + nk
    rent_sim    = facture_sim - cout_sim

    idx = len(df) - 1
    df.loc[idx, "facture"]     = facture_sim
    df.loc[idx, "cout"]        = cout_sim
    df.loc[idx, "rentabilite"] = rent_sim
    df.loc[idx, "paye"]        = 1 if facture_sim > 0 else 0

    model_lr, scaler, metriques = entrainer_modele_probabiliste(df)
    predictions = predire_marges_probabiliste(model_lr, scaler, df, 3)
    profil_dt   = classifier_profil_projet(db, df)

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

Situation réelle  : TJM={last_reel['tjm']}€, facture={last_reel['facture']}€, rentabilité={last_reel['rentabilite']}€
Simulation        : facture={facture_sim:.0f}€, coût={cout_sim:.0f}€, rentabilité={rent_sim:.0f}€
Decision Tree     : classe={profil_dt['classe']}, confiance={profil_dt['confiance']:.0%}
Prévisions 3 mois : {[f"{p['mois']}→{p['marge_probable']:.0f}€" for p in predictions]}
"""
    conseils_ia = generer_conseils_simulation(prompt)

    return convert_numpy({
        "last_reel":  last_reel,           # ✅ ajouté
        "last_ligne_simulee": {
            "facture":     round(facture_sim, 2),
            "cout":        round(cout_sim, 2),
            "rentabilite": round(rent_sim, 2),
            "paye":        paye_last,
        },
        "predictions":  predictions,
        "metriques":    metriques,
        "profil_dt":    profil_dt,
        "conseils_ia":  conseils_ia,
    })