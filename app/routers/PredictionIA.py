import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from dateutil.relativedelta import relativedelta

from ..models import HistoriqueSalarie, Projet
from ..database import get_db
from groq import Groq
from ..config import settings

client = Groq(api_key=settings.chatbot_api_key)
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
# 🔹 DATA PAR PROJET
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


# ─────────────────────────────────────────────
# 🔹 MODÈLE PROBABILISTE
# ─────────────────────────────────────────────
def _ewm_predict(series: pd.Series, n_future: int, span: int = 6) -> list:
    smoothed = series.ewm(span=span, adjust=False).mean()#yaamel smoth ynahi noise ynathef
    last_val = float(smoothed.iloc[-1])
    trend = float(smoothed.iloc[-1] - smoothed.iloc[-3]) / 3 if len(smoothed) >= 3 else 0.0 # لازم على الأقل 3 points باش نحسب trend قدّاش قاعدين نطلعوا ولا نهبطوا كل شهر
    return [max(0.0, last_val + trend * (i + 1)) for i in range(n_future)] #future_value = last_val + trend * (i+1)


def entrainer_modele_probabiliste(df: pd.DataFrame):
    n = len(df)
    X = df[["mois_index"]].values
    y_paye = df["paye"].values

    if len(np.unique(y_paye)) > 1:
        scaler_lr = StandardScaler()
        Xs = scaler_lr.fit_transform(X)
        model_lr = LogisticRegression()
        model_lr.fit(Xs, y_paye)
        prob_paye_hist = model_lr.predict_proba(Xs)[:, 1]
    else:
        scaler_lr = None
        model_lr  = None
        prob_paye_hist = np.full(n, float(y_paye.mean()))

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
    last_index = int(df["mois_index"].max())
    last_date  = df["date"].iloc[-1]

    couts_futurs    = _ewm_predict(df["cout"], n_mois, span=6)
    factures_payees = df[df["paye"] == 1]["facture"]

    if len(factures_payees) >= 2:
        factures_futures = _ewm_predict(factures_payees.reset_index(drop=True), n_mois, span=4)#span 4 5tr montant yetbadel fisaa
    else:
        factures_futures = [float(factures_payees.mean())] * n_mois if len(factures_payees) else [0.0] * n_mois

    predictions = []
    for i in range(n_mois):
        future_index = last_index + i + 1
        future_date  = last_date + relativedelta(months=i + 1)

        if model_lr and scaler_lr:
            X_fut = scaler_lr.transform(np.array([[future_index]]))
            prob = float(model_lr.predict_proba(X_fut)[0, 1])#foction hathra te5o just mois future wtaatin prob deja t3almet men model_lr.fit(Xs, y_paye) taa entrainement fonct
        else:
            prob = float(df["paye"].mean())

        cout    = max(0.0, couts_futurs[i])
        facture = max(0.0, factures_futures[i])#bech taatich haja negatif el max
        marge_probable = prob * (facture - cout) + (1 - prob) * (-cout)

        predictions.append({
            "mois":          future_date.strftime("%Y-%m"),
            "prob_paiement": round(prob, 3),
            "cout_estime":   round(cout, 2),
            "facture_estime": round(facture, 2),
            "marge_probable": round(marge_probable, 2),
            "alerte":        marge_probable < 0,
        })
    return predictions


# ─────────────────────────────────────────────
# 🔹 ANALYSE GLOBALE DE COURBE (tous projets)
# ─────────────────────────────────────────────
def analyser_courbe_globale(evolution: list, kpis: dict, n_mois: int) -> dict:
    """
    Analyse statistique complète de la courbe consolidée :
    tendance, volatilité, momentum, inflexion, régression linéaire.
    """
    if len(evolution) < 2:
        return {}

    marges  = [e["marge"]   for e in evolution]
    couts   = [e["cout"]    for e in evolution]
    mois    = [e["mois"]    for e in evolution]

    # ── Régression linéaire sur la marge ────────────────────────
    x = np.arange(len(marges))
    coeffs = np.polyfit(x, marges, 1)          # [pente, intercept]
    pente   = float(coeffs[0])
    tendance_lineaire = "hausse" if pente > 50 else "baisse" if pente < -50 else "stable"

    # ── Momentum (accélération) ──────────────────────────────────
    if len(marges) >= 4:
        first_half  = np.mean(marges[:len(marges)//2])
        second_half = np.mean(marges[len(marges)//2:])
        momentum = float(second_half - first_half)
        accel = "accélération" if momentum > 0 else "décélération"
    else:
        momentum = float(marges[-1] - marges[0])
        accel = "hausse" if momentum > 0 else "baisse"

    # ── Volatilité ───────────────────────────────────────────────
    volatilite = float(np.std(marges))
    cv = volatilite / (abs(np.mean(marges)) + 1e-6)   # coefficient de variation tathabtheb fel courbe

    # ── Point d'inflexion ────────────────────────────────────────
    inflexion = None
    if len(marges) >= 3:
        deltas = np.diff(marges)
        for i in range(len(deltas) - 1):
            if deltas[i] * deltas[i+1] < 0:   # changement de signe
                inflexion = mois[i + 1]
                break

    # ── Variation totale ─────────────────────────────────────────
    variation_pct = ((marges[-1] - marges[0]) / (abs(marges[0]) + 1e-6)) * 100#شحال تطورنا من الأول للآخر

    # ── Ratio marge / coût ───────────────────────────────────────
    ratio_mc = float(np.mean(marges) / (np.mean(couts) + 1e-6))

    # ── Niveau de risque ─────────────────────────────────────────
    nb_negatifs = sum(1 for m in marges if m < 0)
    if nb_negatifs > len(marges) * 0.4:
        risk = "ÉLEVÉ"
    elif nb_negatifs > 0 or variation_pct < -15:
        risk = "MODÉRÉ"
    else:
        risk = "FAIBLE"

    return {
        "pente":             round(pente, 2),
        "tendance":          tendance_lineaire,
        "momentum":          round(momentum, 2),
        "acceleration":      accel,
        "volatilite":        round(volatilite, 2),
        "cv":                round(cv, 3),
        "inflexion":         inflexion,
        "variation_pct":     round(variation_pct, 1),
        "ratio_marge_cout":  round(ratio_mc, 3),
        "nb_mois_negatifs":  nb_negatifs,
        "risk_level":        risk,
    }


def generer_analyse_courbe_groq(evolution: list, analyse: dict, kpis: dict, n_mois: int) -> str:
    """
    Génère une analyse narrative complète de la courbe globale via Groq.
    """
    marges  = [e["marge"] for e in evolution]
    details = "\n".join([f"  {e['mois']} → marge {e['marge']:.0f} €, coût {e['cout']:.0f} €" for e in evolution])

    prompt = f"""
Tu es un expert senior en finance d'entreprise et en analyse prédictive.

Rédige une **analyse narrative professionnelle** de la courbe financière consolidée de TOUS les projets de l'entreprise sur {n_mois} mois.

--- DONNÉES STATISTIQUES ---
Tendance générale   : {analyse.get('tendance', 'N/A')} (pente {analyse.get('pente', 0):.0f} €/mois)
Variation totale    : {analyse.get('variation_pct', 0):.1f}%
Momentum            : {analyse.get('acceleration', 'N/A')} ({analyse.get('momentum', 0):.0f} €)
Volatilité          : {analyse.get('volatilite', 0):.0f} € (CV = {analyse.get('cv', 0):.2f})
Point d'inflexion   : {analyse.get('inflexion', 'aucun détecté')}
Ratio marge/coût    : {analyse.get('ratio_marge_cout', 0):.2f}
Mois en perte       : {analyse.get('nb_mois_negatifs', 0)} / {len(evolution)}
Niveau de risque    : {analyse.get('risk_level', 'N/A')}

--- KPIs GLOBAUX ---
Marge totale projetée : {kpis.get('marge_totale', 0):.0f} €
Coût total projeté    : {kpis.get('cout_total', 0):.0f} €
Ratio global          : {kpis.get('ratio', 0):.2f}

--- DONNÉES MENSUELLES ---
{details}

--- INSTRUCTIONS ---
Structure ta réponse en HTML avec ces sections EXACTES :
1. <div class="ia-section ia-tendance"> ... </div>  → Analyse de la tendance et de la pente
2. <div class="ia-section ia-risque"> ... </div>    → Évaluation du risque et volatilité
3. <div class="ia-section ia-recommandation"> ... </div> → 2 recommandations actionnables

RÈGLES :
- Maximum 120 mots au total
- Utiliser <strong> pour les chiffres clés uniquement
- Utiliser <span class="chip-pos"> pour positif, <span class="chip-neg"> pour négatif, <span class="chip-num"> pour les valeurs
- Être factuel, professionnel, sans répéter les données brutes
- Ne jamais inventer de données non fournies
"""

    try:
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.15,
            max_tokens=400,
        )
        return chat.choices[0].message.content
    except Exception:
        return "<strong>Analyse indisponible</strong> pour le moment."


# ═══════════════════════════════════════════════════════════════
#  API — prevision par projet
# ═══════════════════════════════════════════════════════════════
@router.get("/prevision-marge/projet/{projet_id}")
def prevision(projet_id: int, db: Session = Depends(get_db)):
    df = get_donnees_projet(db, projet_id)
    if df.empty:
        raise HTTPException(404, "Aucune donnée")
    if len(df) < 2:
        raise HTTPException(400, "Minimum 2 mois requis")

    model_lr, scaler_lr, metriques = entrainer_modele_probabiliste(df)
    predictions = predire_marges_probabiliste(model_lr, scaler_lr, df, n_mois=3)

    result = {
        "projet_id":          projet_id,
        "nb_mois_historique": len(df),
        "metriques":          metriques,
        "historique":         df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records"),
        "predictions":        predictions,
        "alerte_globale":     any(p["alerte"] for p in predictions),
    }
    try:
        result["interpretation"] = generer_analyse_courbe_groq(
            [{"mois": p["mois"], "marge": p["marge_probable"], "cout": p["cout_estime"]} for p in predictions],
            analyser_courbe_globale(
                [{"mois": p["mois"], "marge": p["marge_probable"], "cout": p["cout_estime"]} for p in predictions],
                metriques, 3
            ),
            metriques, 3
        )
    except Exception:
        result["interpretation"] = "Analyse indisponible"

    return convert_numpy(result)


# ═══════════════════════════════════════════════════════════════
#  API — dashboard global (TOUS projets confondus)
# ═══════════════════════════════════════════════════════════════
@router.get("/dashboard-ai")
def dashboard_ai(mois: int = 3, db: Session = Depends(get_db)):
    """
    Retourne l'évolution consolidée de TOUS les projets + analyse globale de courbe.
    """
    projets = db.query(Projet).all()

    evolution_map: dict = {}
    kpi_projets   = []
    total_marge   = 0.0
    total_cout    = 0.0
    nb_projets_traites = 0

    for projet in projets:
        df = get_donnees_projet(db, projet.id)
        if df.empty or len(df) < 2:
            continue

        model_lr, scaler_lr, metriques = entrainer_modele_probabiliste(df)
        preds = predire_marges_probabiliste(model_lr, scaler_lr, df, n_mois=mois)

        nb_projets_traites += 1

        for p in preds:
            k = p["mois"]
            if k not in evolution_map:
                evolution_map[k] = {"mois": k, "marge": 0.0, "cout": 0.0}
            evolution_map[k]["marge"]   += p["marge_probable"]
            evolution_map[k]["cout"]    += p["cout_estime"]
            total_marge += p["marge_probable"]
            total_cout  += p["cout_estime"]

        kpi_projets.append({
            "id":              projet.id,
            "nom":             projet.nom,
            "marge_moyenne":   round(sum(p["marge_probable"] for p in preds) / len(preds), 2),
            "alerte":          any(p["alerte"] for p in preds),
            "taux_paiement":   metriques["taux_paiement_historique"],
            "fiabilite":       metriques["fiabilite"],
        })

    evolution = sorted(evolution_map.values(), key=lambda x: x["mois"])

    kpis = {
        "nb_projets":nb_projets_traites,
        "projets_en_risque":  sum(1 for p in kpi_projets if p["alerte"]),
        "marge_totale":       round(total_marge, 2),
        "cout_total":         round(total_cout, 2),
        "ratio":              round(total_marge / (total_cout + 1e-6), 3),
        "marge_moyenne_projet": round(total_marge / max(nb_projets_traites, 1), 2),
    }

    # ── Analyse statistique de la courbe ────────────────────────
    analyse_courbe = analyser_courbe_globale(evolution, kpis, mois)

    # ── Analyse narrative IA (courbe globale) ───────────────────
    try:
        analyse_ia = generer_analyse_courbe_groq(evolution, analyse_courbe, kpis, mois)
    except Exception:
        analyse_ia = "Analyse indisponible."

    return convert_numpy({
        "kpis":           kpis,
        "evolution":      evolution,
        "projets":        kpi_projets,
        "analyse_courbe": analyse_courbe,
        "analyse_ia":     analyse_ia,
    })         