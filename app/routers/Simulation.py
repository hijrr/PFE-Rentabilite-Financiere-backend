import json
import os
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from groq import Groq
from pydantic import BaseModel
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from starlette.responses import FileResponse
from sklearn.calibration import CalibratedClassifierCV
from ..config import settings
from ..database import get_db
from ..models import HistoriqueSalarie, Projet
from .PredictionIA import convert_numpy

client_groq = Groq(api_key=settings.chatbot_api_key)
router = APIRouter(tags=["Simulation"])


def generer_graphique_comparaison(scores: dict):

    import os
    import matplotlib.pyplot as plt

    output_dir = "static/graphs"
    os.makedirs(output_dir, exist_ok=True)

    # 📊 conversion en %
    modeles = list(scores.keys())
    valeurs = [v * 100 for v in scores.values()]  # 🔥 %

    plt.figure(figsize=(8,5))

    bars = plt.bar(modeles, valeurs)

    plt.title("Comparaison des modèles ML")
    plt.xlabel("Modèles")
    plt.ylabel("Accuracy (%)")
    plt.ylim(0, 100)

    plt.xticks(rotation=20)

    # 📌 afficher le % sur chaque barre
    for bar in bars:
        yval = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width()/2,
            yval + 1,
            f"{round(yval, 1)}%",
            ha="center",
            fontsize=10
        )

    plt.tight_layout()

    image_path = os.path.join(output_dir, "model_comparison.png")

    plt.savefig(image_path)
    plt.close()

    return image_path
@router.get("/simulation/comparer-modeles/graph")
def telecharger_graphique():

    image_path = "static/graphs/model_comparison.png"  # ✅ même chemin

    if not os.path.exists(image_path):
        return {"message": "Image non trouvée. Lance d'abord la comparaison."}

    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename="comparaison_modeles.png"
    )
@router.get("/simulation/comparer-modeles")
def comparer_modeles_mois(
    db: Session = Depends(get_db)
):

    projets = db.query(Projet).all()

    X, y = [], []

    # ─────────────────────────────────────
    # Construction dataset
    # ─────────────────────────────────────
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

            X.append([
                tjm_r,
                jours_r,
                paye_r,
                frais_r,
                snhr_r
            ])

            # Classes
            if rent_r > 500:
                y.append("BON_MOIS")

            elif rent_r < 0:
                y.append("MAUVAIS_MOIS")

            else:
                y.append("MOYEN_MOIS")

    # ─────────────────────────────────────
    # Vérification
    # ─────────────────────────────────────
    if len(X) < 10:
        return {
            "message": "Pas assez de données"
        }

    X = np.array(X)
    y = np.array(y)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    # ─────────────────────────────────────
    # Split train / test
    # ─────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled,
        y,
        test_size=0.3,
        random_state=42
    )
    

    # =====================================================
    # 🌳 Decision Tree
    # =====================================================

    dt = DecisionTreeClassifier(
        max_depth=4,
        random_state=42
    )

    dt.fit(X_train, y_train)

    y_pred_dt = dt.predict(X_test)

    score_dt = accuracy_score(y_test, y_pred_dt)

    print("Decision Tree :", score_dt)

    # =====================================================
    # 👥 KNN
    # =====================================================

    knn = KNeighborsClassifier(
        n_neighbors=3
    )

    knn.fit(X_train, y_train)

    y_pred_knn = knn.predict(X_test)

    score_knn = accuracy_score(y_test, y_pred_knn)

    print("KNN :", score_knn)

    # =====================================================
    # 📈 SVC
    # =====================================================

    svc = SVC(
        probability=True
    )

    svc.fit(X_train, y_train)

    y_pred_svc = svc.predict(X_test)

    score_svc = accuracy_score(y_test, y_pred_svc)

    print("SVC :", score_svc)

    # =====================================================
    # 🔔 GaussianNB
    # =====================================================

    gnb = GaussianNB()

    gnb.fit(X_train, y_train)

    y_pred_gnb = gnb.predict(X_test)

    score_gnb = accuracy_score(y_test, y_pred_gnb)

    print("GaussianNB :", score_gnb)

    # ─────────────────────────────────────
    # Choix meilleur modèle
    # ─────────────────────────────────────

    scores = {
        "Decision Tree": score_dt,
        "KNN": score_knn,
        "SVC": score_svc,
        "GaussianNB": score_gnb
    }

    meilleur_modele = max(scores, key=scores.get)

    meilleur_score = scores[meilleur_modele]
    image_path = generer_graphique_comparaison(scores)
    return {
        "Decision Tree": round(score_dt, 3),
        "KNN": round(score_knn, 3),
        "SVC": round(score_svc, 3),
        "GaussianNB": round(score_gnb, 3),
        "meilleur_modele": meilleur_modele,
        "meilleur_score": round(meilleur_score, 3)
    }
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
# GAUSSIAN NAIVE BAYES SUR LES MOIS HISTORIQUES
# ══════════════════════════════════════════════════════════

def entrainer_gaussian_mois(db: Session):

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

            net_avant_impot_r = float(r.netAvantImpot or 0)
            snhr_r = float(r.salaireNetHorsRepas or (net_avant_impot_r - float(r.repasRestaurant or 0)))
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

    X = np.array(X)
    y = np.array(y)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled,
        y,
        test_size=0.2,
        random_state=42,
    )

    model = GaussianNB()
    model.fit(X_train, y_train)

    # (optionnel mais très utile)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print("Accuracy GaussianNB:", acc)

    return model,scaler
# ══════════════════════════════════════════════════════════
# CLASSIFICATION HYBRIDE DU MOIS SIMULÉ
# ══════════════════════════════════════════════════════════

def appliquer_regle_financiere(rentabilite: float) -> Optional[str]:
    if rentabilite > 500:
        return "BON_MOIS"
    if rentabilite < 0:
        return "MAUVAIS_MOIS"
    return None


def classifier_cas_mois(
    model,
    scaler,
    tjm: float,
    jours: float,
    paye: float,
    frais_total: float,
    salaire_net_hors_repas: float,
    rentabilite: float,
):
    classe_regle = appliquer_regle_financiere(rentabilite)

    if model is None:
        classe_fallback = classe_regle or "MOYEN_MOIS"
        return {
            "classe_ml": classe_fallback,
            "confiance": 1.0,
            "probas": {},
        }

    X = np.array([[tjm, jours, paye, frais_total, salaire_net_hors_repas]])
    X_scaled = scaler.transform(X) 
    classe_ml = model.predict(X_scaled)[0]
    probas = model.predict_proba(X_scaled)[0]#fe rapport vecteur yaani table numpy
    return {
        "classe_ml": classe_ml,
        "confiance": round(float(np.max(probas)), 3),
        "probas": {c: round(float(p), 3) for c, p in zip(model.classes_, probas)},
    }


def classifier_mois_simule(
    db: Session,
    tjm: float,
    jours: float,
    repas: float,
    nf: float,
    nk: float,
    snhr_sim: float,
    net_avant_impot: float,
):
    model, scaler = entrainer_gaussian_mois(db)

   
    # salaireNetHorsRepas n'est jamais saisi par l'utilisateur.
    # Il dépend directement du netAvantImpot réel du dernier mois et du repas simulé.
    salaire_net_hors_repas = net_avant_impot - repas
    
    frais_sim = repas + nf + nk
    facture_brute = tjm * jours
    total_percu = salaire_net_hors_repas + repas + nf + nk
    cout_sim = total_percu

    rent_paye = facture_brute - total_percu
    rent_non_paye = 0 - total_percu

    classification_paye = classifier_cas_mois(
        model=model,
        scaler=scaler,
        tjm=tjm,
        jours=jours,
        paye=1.0,
        frais_total=frais_sim,
        salaire_net_hors_repas=salaire_net_hors_repas,
        rentabilite=rent_paye,
    )
    classification_non_paye = classifier_cas_mois(
        model=model,scaler=scaler,
        tjm=tjm,
        jours=jours,
        paye=0.0,
        frais_total=frais_sim,
        salaire_net_hors_repas=salaire_net_hors_repas,
        rentabilite=rent_non_paye,
    )

    return {
        "cas_paye": {
            **classification_paye,
            "rentabilite": round(rent_paye, 2),
            "totaleFacture": round(facture_brute, 2),
        },
        "cas_non_paye": {
            **classification_non_paye,
            "rentabilite": round(rent_non_paye, 2),
            "totaleFacture": 0.0,
        },
        "facture_brute": round(facture_brute, 2),
        "cout_sim": round(cout_sim, 2),
        "salaire_net_hors_repas": round(salaire_net_hors_repas, 2),
        "frais_total": round(frais_sim, 2),
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
            max_tokens=900,
        )

        content = chat.choices[0].message.content

        try:
            cleaned = content.replace("json", "").replace("", "").strip()
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

    last = rows[-1]
    net_avant_impot_reel = float(last.netAvantImpot or 0)
    repas_reel = float(last.repasRestaurant or 0)
    salaire_net_hors_repas_reel = net_avant_impot_reel - repas_reel

    last_reel = {
        "tjm": float(last.tjm or 0),
        "jours": float(last.joursTravailles or 0),
        "repas": repas_reel,
        "note_frais": float(last.totalNoteFrais or 0),
        "note_kilo": float(last.totalNoteKilometrique or 0),
        "net_avant_impot": net_avant_impot_reel,
        "salaire_net_hors_repas": salaire_net_hors_repas_reel,
        "facture": float(last.totaleFacture or 0),
        "cout": float(last.totalePercu or 0),
        "rentabilite": float(last.rentabilite or 0),
    }

    tjm = params.tjm if params.tjm is not None else last_reel["tjm"]
    jours = params.jours_travailles if params.jours_travailles is not None else last_reel["jours"]
    repas = params.repas_restaurant if params.repas_restaurant is not None else last_reel["repas"]
    nf = params.total_note_frais if params.total_note_frais is not None else last_reel["note_frais"]
    nk = params.total_note_kilometrique if params.total_note_kilometrique is not None else last_reel["note_kilo"]

    facture_brute = tjm * jours

    # Le salaire net hors repas est calcule, pas simule :
    # l'utilisateur modifie les repas, puis on recalcule netAvantImpot - repasRestaurant.
    net_avant_impot = last_reel["net_avant_impot"]
    salaire_net_hors_repas = net_avant_impot - repas
    total_percu = salaire_net_hors_repas + repas + nf + nk
    cout_sim = total_percu
    rent_paye = facture_brute - total_percu
    rent_non_paye = 0 - total_percu

    profil_dt = classifier_mois_simule(
        db=db,
        tjm=tjm,
        jours=jours,
        repas=repas,
        nf=nf,
        nk=nk,
        snhr_sim=salaire_net_hors_repas,
        net_avant_impot=net_avant_impot,
    )
    print("Profil DT :", profil_dt)
    tjm_min_rentable = round(cout_sim / jours, 2) if jours > 0 else None
    tjm_min_bon_mois = round((cout_sim + 500) / jours, 2) if jours > 0 else None
    jours_min_rentable = int(np.ceil(cout_sim / tjm)) if tjm > 0 else None
    jours_min_bon_mois = int(np.ceil((cout_sim + 500) / tjm)) if tjm > 0 else None
    ecart_tjm = round(tjm - last_reel["tjm"], 2)
    ecart_jours = round(jours - last_reel["jours"], 2)
    ecart_frais = round((repas + nf + nk) - (last_reel["repas"] + last_reel["note_frais"] + last_reel["note_kilo"]), 2)

    prompt = f"""
Tu es un expert senior en rentabilité de projets de conseil.
Réponds UNIQUEMENT en JSON valide, sans texte hors JSON.

Structure obligatoire :
{{
  "verdict": "positif"|"négatif"|"neutre",
  "resume": "résumé clair en 1 phrase, max 25 mots",
  "conseils": [
    {{"type":"action|alerte|optimisation","titre":"max 6 mots","detail":"conseil précis avec valeur chiffrée si possible, max 45 mots","priorite":"haute|moyenne|faible"}}
  ],
  "conseil_tjm": "conseil TJM ou null",
  "conseil_jours": "conseil jours ou null",
  "seuil_rentabilite": "seuil ou null"
}}

Objectif :
- analyser uniquement le dernier mois du projet ;
- dire clairement quoi augmenter et quoi diminuer par rapport au mois réel ;
- proposer des actions concrètes, chiffrées et non répétitives ;
- alerter sur les risques réels, surtout le non-paiement.

Données réelles du dernier mois :
- TJM : {last_reel['tjm']:.2f}€
- Jours travaillés : {last_reel['jours']:.2f}
- Repas restaurant : {last_reel['repas']:.2f}€
- Notes de frais : {last_reel['note_frais']:.2f}€
- Notes kilométriques : {last_reel['note_kilo']:.2f}€
- Net avant impôt : {last_reel['net_avant_impot']:.2f}€
- Salaire net hors repas calculé : {last_reel['salaire_net_hors_repas']:.2f}€
- Coût total réel : {last_reel['cout']:.2f}€
- Facture réelle : {last_reel['facture']:.2f}€
- Rentabilité réelle : {last_reel['rentabilite']:.2f}€

Données simulées :
- TJM simulé : {tjm:.2f}€ ({ecart_tjm:+.2f}€ vs réel)
- Jours simulés : {jours:.2f} ({ecart_jours:+.2f} vs réel)
- Repas simulés : {repas:.2f}€
- Notes de frais simulées : {nf:.2f}€
- Notes kilométriques simulées : {nk:.2f}€
- Ecart frais totaux vs réel : {ecart_frais:+.2f}€
- Salaire net hors repas calculé : {salaire_net_hors_repas:.2f}€
- Coût total simulé : {cout_sim:.2f}€
- Facture brute simulée : {facture_brute:.2f}€

Résultats financiers :
- Si payé : rentabilité {profil_dt['cas_paye']['rentabilite']:.2f}€,classe ML {profil_dt['cas_paye']['classe_ml']}, confiance {profil_dt['cas_paye']['confiance']}
- Probabilités ML payé : {profil_dt['cas_paye']['probas']}
- Si non payé : rentabilité {profil_dt['cas_non_paye']['rentabilite']:.2f}€, classe ML {profil_dt['cas_non_paye']['classe_ml']}, confiance {profil_dt['cas_non_paye']['confiance']}
- Probabilités ML non payé : {profil_dt['cas_non_paye']['probas']}

Seuils calculés :
- TJM minimum pour rentabilité positive avec {jours:.2f} jours : {tjm_min_rentable}
- TJM minimum pour dépasser 500€ de rentabilité : {tjm_min_bon_mois}
- Jours minimum pour rentabilité positive avec TJM {tjm:.2f}€ : {jours_min_rentable}
- Jours minimum pour dépasser 500€ de rentabilité : {jours_min_bon_mois}

Contraintes de réponse :
- Fournis 3 à 5 conseils maximum.
- Chaque conseil doit dire quoi augmenter ou diminuer quand c'est pertinent.
- Evite les conseils vagues comme "optimiser les coûts" sans valeur ni raison.
- Si les frais sont élevés, précise lesquels réduire en priorité.
- Si la rentabilité est négative, explique la cause principale.
"""

    conseils_ia = generer_conseils_simulation(prompt)

    return convert_numpy({
        "last_reel": last_reel,
        "simulation": {
            "facture_brute": round(facture_brute, 2),
            "facture_sim": round(facture_brute, 2),
            "cout": round(cout_sim, 2),
            "salaire_net_hors_repas": round(salaire_net_hors_repas, 2),
            "net_hors_repas": round(salaire_net_hors_repas, 2),
            "total_percu": round(total_percu, 2),
            "rentabilite": round(rent_paye, 2),
            "rent_paye": round(rent_paye, 2),
            "rent_non_paye": round(rent_non_paye, 2),
            "seuils": {
                "tjm_min_rentable": tjm_min_rentable,
                "tjm_min_bon_mois": tjm_min_bon_mois,
                "jours_min_rentable": jours_min_rentable,
                "jours_min_bon_mois": jours_min_bon_mois,
            },
        },
        "profil_dt": profil_dt,
        "conseils_ia": conseils_ia,
    })
    
    