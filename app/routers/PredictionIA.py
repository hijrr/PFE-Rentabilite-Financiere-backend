import pandas as pd
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from ..models import HistoriqueSalarie
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from fastapi import APIRouter, Depends, HTTPException
from ..database import get_db
import numpy as np
from dateutil.relativedelta import relativedelta

router = APIRouter(tags=["PredictionIA"])


# ─────────────────────────────────────────────
# 🔹 Conversion numpy → JSON
# ─────────────────────────────────────────────
def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


FEATURES = ["mois_index"]
TARGET   = "rentabilite"


# ─────────────────────────────────────────────
# 🔹 Récupération données depuis DB
# ─────────────────────────────────────────────
def get_donnees_projet(db: Session, projet_id: int) -> pd.DataFrame:
    rows = db.query(
        HistoriqueSalarie.date,
        HistoriqueSalarie.totalePercu,
        HistoriqueSalarie.totaleFacture,
        HistoriqueSalarie.rentabilite,
    ).filter(
        HistoriqueSalarie.projet_id == projet_id,
        HistoriqueSalarie.rentabilite != None,
        HistoriqueSalarie.totalePercu != None,
        HistoriqueSalarie.totaleFacture != None,
    ).order_by(HistoriqueSalarie.date).all()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["date", "totalePercu", "totaleFacture", TARGET])
    df[["totalePercu", "totaleFacture"]] = df[["totalePercu", "totaleFacture"]].fillna(0)

    # Index temporel simple
    df["mois_index"] = range(len(df))

    return df


# ─────────────────────────────────────────────
# 🔹 Entraînement modèles
# ─────────────────────────────────────────────
def entrainer_modele(df: pd.DataFrame):
    X = df[["mois_index"]].values

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Modèle coût
    model_percu = LinearRegression()
    model_percu.fit(X_scaled, df["totalePercu"].values)

    # Modèle CA (seulement mois payés)
    df_paye = df[df["totaleFacture"] > 0]

    if len(df_paye) >= 2:
        X_paye_scaled = scaler.transform(df_paye[["mois_index"]].values)
        model_facture = LinearRegression()
        model_facture.fit(X_paye_scaled, df_paye["totaleFacture"].values)
    else:
        model_facture = None

    # ── Métriques (approx)
    percu_pred   = model_percu.predict(X_scaled)
    facture_pred = (
        model_facture.predict(X_scaled)
        if model_facture else df["totaleFacture"].values
    )

    marge_pred = facture_pred - percu_pred
    marge_reel = df["rentabilite"].values

    metriques = {
        "r2":        round(float(r2_score(marge_reel, marge_pred)), 3),
        "mae":       round(float(mean_absolute_error(marge_reel, marge_pred)), 2),
        "nb_mois":   len(df),
        "fiabilite": "faible" if len(df) < 6 else "bonne"
    }

    return model_percu, model_facture, scaler, metriques


# ─────────────────────────────────────────────
# 🔹 Prédiction intelligente
# ─────────────────────────────────────────────
def predire_marges(model_percu, model_facture, scaler, df: pd.DataFrame, n_mois: int = 3) -> list:
    dernier_index = int(df["mois_index"].max())
    derniere_date = pd.to_datetime(df["date"].iloc[-1])

    # 🔥 taux de paiement
    taux_paiement = len(df[df["totaleFacture"] > 0]) / len(df)

    # fallback CA
    moy_facture = float(df[df["totaleFacture"] > 0]["totaleFacture"].mean() or 0)

    predictions = []

    for i in range(1, n_mois + 1):
        date_str    = (derniere_date + relativedelta(months=i)).strftime("%Y-%m")
        index_futur = dernier_index + i

        X_futur  = np.array([[index_futur]])
        X_scaled = scaler.transform(X_futur)

        # Coût
        percu_futur = float(model_percu.predict(X_scaled)[0])
        percu_futur = max(0.0, percu_futur)

        # CA
        if model_facture is not None:
            facture_futur = float(model_facture.predict(X_scaled)[0])
            facture_futur = max(0.0, facture_futur)
        else:
            facture_futur = moy_facture

        # Marges
        marge_si_paye     = facture_futur - percu_futur
        marge_si_non_paye = -percu_futur

        # 🔥 marge intelligente
        marge_probable = (
            taux_paiement * marge_si_paye +
            (1 - taux_paiement) * marge_si_non_paye
        )

        predictions.append({
            "mois":              date_str,
            "marge_si_paye":     round(marge_si_paye, 2),
            "marge_si_non_paye": round(marge_si_non_paye, 2),
            "marge_probable":    round(marge_probable, 2),
            "cout_estime":       round(percu_futur, 2),
            "ca_estime":         round(facture_futur, 2),
            "taux_paiement":     round(taux_paiement, 2),
            "alerte": bool(marge_si_paye < 0 or marge_si_non_paye < 0)
        })

    return predictions
# ─────────────────────────────────────────────
# 🔹 API endpoint
# ─────────────────────────────────────────────
@router.get("/prevision-marge/projet/{projet_id}")
def prevision_marge_par_projet(projet_id: int, db: Session = Depends(get_db)):
    df = get_donnees_projet(db, projet_id)

    if df.empty:
        raise HTTPException(status_code=404, detail="Aucune donnée trouvée.")
    if len(df) < 2:
        raise HTTPException(status_code=400, detail=f"Seulement {len(df)} mois. Minimum : 2.")

    model_percu, model_facture, scaler, metriques = entrainer_modele(df)
    predictions = predire_marges(model_percu, model_facture, scaler, df)

    result = {
        "projet_id":          projet_id,
        "nb_mois_historique": len(df),
        "metriques":          metriques,
        "taux_paiement_global": round(len(df[df["totaleFacture"] > 0]) / len(df), 2),
        "message_fiabilite": (
            "Prédiction indicative (moins de 6 mois)"
            if len(df) < 6 else "Prédiction fiable"
        ),
        "historique": df[["date", "totalePercu", "totaleFacture", "rentabilite"]]
                        .to_dict(orient="records"),
        "predictions":    predictions,
        "alerte_globale": bool(any(p["alerte"] for p in predictions))
    }

    return convert_numpy(result)