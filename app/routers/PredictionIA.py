import pandas as pd
import numpy as np

from prophet import Prophet
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from dateutil.relativedelta import relativedelta

from ..models import HistoriqueSalarie, Projet
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
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return 0.0
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

    df["cout"]        = pd.to_numeric(df["cout"],        errors="coerce").fillna(0)
    df["facture"]     = pd.to_numeric(df["facture"],     errors="coerce").fillna(0)
    df["rentabilite"] = pd.to_numeric(df["rentabilite"], errors="coerce").fillna(0)
    df["date"]        = pd.to_datetime(df["date"])

    # Agrégation mensuelle (une ligne par mois)
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df = (
        df.groupby("month")
        .agg({"cout": "sum", "facture": "sum", "rentabilite": "sum"})
        .reset_index()
        .rename(columns={"month": "date"})
    )
    df["mois_index"] = np.arange(len(df))
    df["paye"]       = (df["facture"] > 0).astype(int)

    return df


# ═══════════════════════════════════════════════════════════════
#  MODÈLE 1 — PROBABILISTE BINAIRE  (modèle principal)
# ═══════════════════════════════════════════════════════════════

def _ewm_predict(series: pd.Series, n_future: int, span: int = 6) -> list[float]:
    """
    Moyenne mobile exponentielle : prédit les n_future prochaines valeurs
    en repartant de la dernière valeur lissée.
    """
    smoothed = series.ewm(span=span, adjust=False).mean()
    last_val = float(smoothed.iloc[-1])
    # Légère tendance basée sur les 3 derniers mois lissés
    if len(smoothed) >= 3:
        trend = float(smoothed.iloc[-1] - smoothed.iloc[-3]) / 3
    else:
        trend = 0.0
    return [max(0.0, last_val + trend * (i + 1)) for i in range(n_future)]


def entrainer_modele_probabiliste(df: pd.DataFrame):
    """
    Modèle en deux questions :
      Q1 — Le client va-t-il payer ce mois ? → LogisticRegression sur mois_index
      Q2 — Combien (coût & facture) ?         → EWM sur séries historiques
    """
    n = len(df)
    X = df[["mois_index"]].values
    y_paye = df["paye"].values

    # ── Q1 : probabilité de paiement ─────────────────────────────
    if len(np.unique(y_paye)) > 1:
        scaler_lr = StandardScaler()
        Xs = scaler_lr.fit_transform(X)
        model_lr = LogisticRegression()
        model_lr.fit(Xs, y_paye)
        prob_paye_hist = model_lr.predict_proba(Xs)[:, 1]
    else:
        # Tous les mois ont le même statut → pas assez de variance
        scaler_lr = None
        model_lr  = None
        prob_paye_hist = np.full(n, float(y_paye.mean()))

    # ── Métriques ─────────────────────────────────────────────────
    # On reconstruit la marge prédite in-sample pour évaluer
    mean_facture_paye = df[df["paye"] == 1]["facture"].mean() if df["paye"].sum() > 0 else 0.0
    mean_cout         = df["cout"].mean()

    marge_pred = prob_paye_hist * (df["facture"].values - df["cout"].values) + \
             (1 - prob_paye_hist) * (-df["cout"].values)
    y_rent = df["rentabilite"].values

    r2  = float(r2_score(y_rent, marge_pred))  if n >= 2 else 0.0
    mae = float(mean_absolute_error(y_rent, marge_pred)) if n >= 1 else 0.0

    metriques = {
        "r2":       round(r2,  3),
        "mae":      round(mae, 2),
        "nb_mois":  n,
        "fiabilite": "faible" if n < 6 else "moyenne" if n < 12 else "bonne",
        "modele":   "Probabiliste Binaire",
        "taux_paiement_historique": round(float(y_paye.mean()), 3),
    }

    return model_lr, scaler_lr, metriques


def predire_marges_probabiliste(model_lr, scaler_lr, df: pd.DataFrame, n_mois: int = 3):
    """
    Prédit n_mois de marges avec intervalle de confiance bootstrap simple.
    """
    last_index = int(df["mois_index"].max())
    last_date  = df["date"].iloc[-1]

    # ── EWM sur coût et facture (mois payés uniquement) ───────────
    couts_futurs    = _ewm_predict(df["cout"],                        n_mois, span=6)
    factures_payees = df[df["paye"] == 1]["facture"]
    if len(factures_payees) >= 2:
        factures_futures = _ewm_predict(factures_payees.reset_index(drop=True), n_mois, span=4)
    else:
        factures_futures = [float(factures_payees.mean())] * n_mois if len(factures_payees) else [0.0] * n_mois

    # ── Std historique pour intervalles de confiance ──────────────
    std_cout    = float(df["cout"].std())    if len(df) > 1 else 0.0
    std_facture = float(factures_payees.std()) if len(factures_payees) > 1 else 0.0

    predictions = []

    for i in range(n_mois):
        future_index = last_index + i + 1
        future_date  = last_date + relativedelta(months=i + 1)

        # ── Q1 : prob de paiement ─────────────────────────────────
        if model_lr and scaler_lr:
            X_fut = scaler_lr.transform(np.array([[future_index]]))
            prob  = float(model_lr.predict_proba(X_fut)[0, 1])
        else:
            prob = float(df["paye"].mean())

        # ── Q2 : estimations ──────────────────────────────────────
        cout    = max(0.0, couts_futurs[i])
        facture = max(0.0, factures_futures[i])

        # Intervalles ±1.5σ (≈ 87% de confiance)
        cout_lower    = max(0.0, cout    - 1.5 * std_cout)
        cout_upper    = max(0.0, cout    + 1.5 * std_cout)
        facture_lower = max(0.0, facture - 1.5 * std_facture)
        facture_upper = max(0.0, facture + 1.5 * std_facture)

        marge_si_paye    = facture - cout
        marge_si_non_paye = -cout
        marge_probable   = prob * marge_si_paye + (1 - prob) * marge_si_non_paye

        marge_lower = facture_lower - cout_upper
        marge_upper = facture_upper - cout_lower

        predictions.append({
            "mois":               future_date.strftime("%Y-%m"),
            "prob_paiement":      round(prob, 3),
            "cout_estime":        round(cout, 2),
            "cout_lower":         round(cout_lower, 2),
            "cout_upper":         round(cout_upper, 2),
            "facture_estime":     round(facture, 2),
            "facture_lower":      round(facture_lower, 2),
            "facture_upper":      round(facture_upper, 2),
            "marge_si_paye":      round(marge_si_paye, 2),
            "marge_si_non_paye":  round(marge_si_non_paye, 2),
            "marge_probable":     round(marge_probable, 2),
            "marge_lower":        round(marge_lower, 2),
            "marge_upper":        round(marge_upper, 2),
            "taux_paiement":      round(prob, 2),
            "alerte":             marge_si_paye < 0,
        })

    return predictions


# ═══════════════════════════════════════════════════════════════
#  MODÈLE 2 — PROPHET  (comparaison)
# ═══════════════════════════════════════════════════════════════

def entrainer_et_predire_prophet(df: pd.DataFrame, n_mois: int = 3):
    """
    Entraîne Prophet et retourne les prédictions + métriques.
    Utilisé uniquement en comparaison.
    """
    try:
        # Modèle coût
        df_cout = df[["date", "cout"]].rename(columns={"date": "ds", "cout": "y"})
        m_cout = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.5,
            n_changepoints=min(8, len(df) // 2),
            interval_width=0.80,
        )
        m_cout.fit(df_cout)

        # Modèle facture (mois payés uniquement)
        df_valid   = df[df["facture"] > 0]
        m_facture  = None
        if len(df_valid) >= 3:
            df_f = df_valid[["date", "facture"]].rename(columns={"date": "ds", "facture": "y"})
            m_facture = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=False,
                daily_seasonality=False,
                changepoint_prior_scale=0.5,
                n_changepoints=min(5, len(df_valid) // 2),
                interval_width=0.80,
            )
            m_facture.fit(df_f)

        # Dates futures
        last_date    = df["date"].iloc[-1]
        future_dates = [last_date + relativedelta(months=i) for i in range(1, n_mois + 1)]
        future_df    = pd.DataFrame({"ds": future_dates})

        fc_cout = m_cout.predict(future_df)
        fc_fact = m_facture.predict(future_df) if m_facture else None

        taux    = float(df["paye"].mean())
        mean_f  = float(df_valid["facture"].mean()) if len(df_valid) else 0.0

        preds_prophet = []
        for i in range(n_mois):
            cout    = max(0.0, float(fc_cout["yhat"].iloc[i]))
            facture = max(0.0, float(fc_fact["yhat"].iloc[i])) if fc_fact is not None else mean_f

            preds_prophet.append({
                "mois":           future_dates[i].strftime("%Y-%m"),
                "cout_estime":    round(cout, 2),
                "facture_estime": round(facture, 2),
                "marge_si_paye":  round(facture - cout, 2),
                "marge_probable": round(taux * (facture - cout) + (1 - taux) * (-cout), 2),
                "marge_lower":    round(max(0.0, float(fc_fact["yhat_lower"].iloc[i])) - max(0.0, float(fc_cout["yhat_upper"].iloc[i])) if fc_fact is not None else -cout, 2),
                "marge_upper":    round(max(0.0, float(fc_fact["yhat_upper"].iloc[i])) - max(0.0, float(fc_cout["yhat_lower"].iloc[i])) if fc_fact is not None else facture - cout, 2),
            })

        # Métriques Prophet in-sample
        fc_train = m_cout.predict(m_cout.make_future_dataframe(periods=0, freq="MS"))
        y_rent   = df["rentabilite"].values
        n        = min(len(fc_train), len(y_rent))
        r2_p     = float(r2_score(y_rent[:n], fc_train["yhat"].values[:n])) if n >= 2 else 0.0

        metriques_prophet = {
            "r2":     round(r2_p, 3),
            "modele": "Prophet",
        }

        return preds_prophet, metriques_prophet

    except Exception as e:
        return [], {"r2": None, "modele": "Prophet", "erreur": str(e)}


# ═══════════════════════════════════════════════════════════════
#  API
# ═══════════════════════════════════════════════════════════════

@router.get("/prevision-marge/projet/{projet_id}")
def prevision(projet_id: int, db: Session = Depends(get_db)):

    df = get_donnees_projet(db, projet_id)

    if df.empty:
        raise HTTPException(404, "Aucune donnée")
    if len(df) < 2:
        raise HTTPException(400, "Minimum 2 mois requis")

    # ── Modèle principal ──────────────────────────────────────────
    model_lr, scaler_lr, metriques = entrainer_modele_probabiliste(df)
    predictions = predire_marges_probabiliste(model_lr, scaler_lr, df, n_mois=3)

    # ── Comparaison Prophet ───────────────────────────────────────
    preds_prophet, metriques_prophet = entrainer_et_predire_prophet(df, n_mois=3)

    return convert_numpy({
        "projet_id":            projet_id,
        "nb_mois_historique":   len(df),
        "metriques":            metriques,
        "historique":           df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records"),
        "predictions":          predictions,
        "alerte_globale":       any(p["alerte"] for p in predictions),

        # Comparaison Prophet
        "comparaison_prophet": {
            "metriques":   metriques_prophet,
            "predictions": preds_prophet,
        }
    })


@router.get("/dashboard-ai")
def dashboard_ai(mois: int = 3, db: Session = Depends(get_db)):

    projets      = db.query(Projet).all()
    evolution    = []
    kpi_projets  = []
    total_facture = 0
    total_cout    = 0

    for projet in projets:

        df = get_donnees_projet(db, projet.id)
        if df.empty or len(df) < 2:
            continue

        model_lr, scaler_lr, _ = entrainer_modele_probabiliste(df)
        preds = predire_marges_probabiliste(model_lr, scaler_lr, df, n_mois=mois)

        facture_proj = 0
        cout_proj    = 0

        for i, p in enumerate(preds):
            if len(evolution) <= i:
                evolution.append({"mois": p["mois"], "marge": 0, "cout": 0, "facture": 0})
            evolution[i]["marge"]   += p["facture_estime"] - p["cout_estime"]
            evolution[i]["cout"]    += p["cout_estime"]
            evolution[i]["facture"] += p["facture_estime"]
            facture_proj += p["facture_estime"]
            cout_proj    += p["cout_estime"]

        kpi_projets.append({
            "id":            projet.id,
            "nom":           projet.nom,
            "marge_moyenne": (facture_proj - cout_proj) / len(preds),
            "alerte":        any(p["alerte"] for p in preds),
        })

        total_facture += facture_proj
        total_cout    += cout_proj

    return convert_numpy({
        "kpis": {
            "nb_projets":          len(kpi_projets),
            "projets_en_risque":   len([p for p in kpi_projets if p["alerte"]]),
            "marge_globale_moyenne": total_facture - total_cout,
        },
        "evolution": evolution,
        "projets":   kpi_projets,
    })