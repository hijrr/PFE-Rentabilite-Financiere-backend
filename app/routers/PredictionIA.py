import pandas as pd
import numpy as np

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from dateutil.relativedelta import relativedelta

from ..models import HistoriqueSalarie
from ..database import get_db

router = APIRouter(tags=["PredictionIA"])


# ─────────────────────────────────────────────
# 🔹 JSON SAFE
# ─────────────────────────────────────────────
def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    if isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    return obj


# ─────────────────────────────────────────────
# 🔹 DATA
# ─────────────────────────────────────────────
def get_donnees_projet(db: Session, projet_id: int):
    rows = db.query(
        HistoriqueSalarie.date,
        HistoriqueSalarie.totalePercu,
        HistoriqueSalarie.totaleFacture,
        HistoriqueSalarie.rentabilite,
    ).filter(
        HistoriqueSalarie.projet_id == projet_id
    ).order_by(HistoriqueSalarie.date).all()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["date", "cout", "facture", "rentabilite"])

    # CLEAN
    df["cout"] = df["cout"].fillna(0)
    df["facture"] = df["facture"].fillna(0)
    df["rentabilite"] = df["rentabilite"].fillna(0)

    df["mois_index"] = np.arange(len(df))

    return df


# ─────────────────────────────────────────────
# 🔹 TRAIN (CORRIGÉ)
# ─────────────────────────────────────────────
def entrainer_modele(df: pd.DataFrame):

    X = df[["mois_index"]].values
    y_cout = df["cout"].values
    y_facture = df["facture"].values
    y_rentabilite = df["rentabilite"].values

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    # modèle coût
    model_cout = LinearRegression()
    model_cout.fit(Xs, y_cout)

    # modèle facture (important fallback)
    model_facture = None
    df_valid = df[df["facture"] > 0]

    if len(df_valid) >= 3:
        Xf = scaler.transform(df_valid[["mois_index"]].values)
        model_facture = LinearRegression()
        model_facture.fit(Xf, df_valid["facture"].values)

    # prédictions train
    cout_pred = model_cout.predict(Xs)

    if model_facture:
        facture_pred = model_facture.predict(Xs)
    else:
        facture_pred = y_facture

    marge_pred = facture_pred - cout_pred

    # métriques corrigées
    metriques = {
        "r2": round(float(r2_score(y_rentabilite, marge_pred)), 3),
        "mae": round(float(mean_absolute_error(y_rentabilite, marge_pred)), 2),
        "nb_mois": len(df),
        "fiabilite": "faible" if len(df) < 6 else "moyenne"
    }

    return model_cout, model_facture, scaler, metriques


# ─────────────────────────────────────────────
# 🔹 PREDICTION (AMÉLIORÉE)
# ─────────────────────────────────────────────
def predire_marges(model_cout, model_facture, scaler, df, n_mois=3):

    last_index = int(df["mois_index"].max())
    last_date = pd.to_datetime(df["date"].iloc[-1])

    taux_paiement = len(df[df["facture"] > 0]) / len(df)

    mean_facture = df[df["facture"] > 0]["facture"].mean()
    mean_facture = 0 if np.isnan(mean_facture) else mean_facture

    predictions = []

    for i in range(1, n_mois + 1):

        x_future = scaler.transform(np.array([[last_index + i]]))

        cout = float(model_cout.predict(x_future)[0])
        cout = max(0, cout)

        if model_facture:
            facture = float(model_facture.predict(x_future)[0])
        else:
            facture = mean_facture

        facture = max(0, facture)

        # marges
        marge_si_paye = facture - cout
        marge_si_non_paye = -cout

        # logique probabiliste simple
        marge_probable = (
            taux_paiement * marge_si_paye +
            (1 - taux_paiement) * marge_si_non_paye
        )

        predictions.append({
            "mois": (last_date + relativedelta(months=i)).strftime("%Y-%m"),
            "cout_estime": round(cout, 2),
            "facture_estime": round(facture, 2),
            "marge_si_paye": round(marge_si_paye, 2),
            "marge_si_non_paye": round(marge_si_non_paye, 2),
            "marge_probable": round(marge_probable, 2),
            "taux_paiement": round(taux_paiement, 2),
            "alerte": marge_si_paye < 0
        })

    return predictions


# ─────────────────────────────────────────────
# 🔹 API
# ─────────────────────────────────────────────
@router.get("/prevision-marge/projet/{projet_id}")
def prevision(projet_id: int, db: Session = Depends(get_db)):

    df = get_donnees_projet(db, projet_id)

    if df.empty:
        raise HTTPException(404, "Aucune donnée")

    if len(df) < 2:
        raise HTTPException(400, "Minimum 2 mois requis")

    model_cout, model_facture, scaler, metrics = entrainer_modele(df)
    predictions = predire_marges(model_cout, model_facture, scaler, df)

    return convert_numpy({
        "projet_id": projet_id,
        "nb_mois_historique": len(df),
        "metriques": metrics,
        "historique": df.to_dict(orient="records"),
        "predictions": predictions,
        "alerte_globale": any(p["alerte"] for p in predictions)
    })