from datetime import datetime
from typing import Optional,List

from pydantic import BaseModel, ConfigDict

class LoginRequest(BaseModel):
    username: str
    password: str
    
class TokenData(BaseModel):
    id: Optional[int] = None
    
class Token(BaseModel):
    access_token: str
    token_type: str
    
class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    
    
class SalariesBase(BaseModel):
    username: str
    role_id: int
    email: str
    date_entree: datetime
    tjm: Optional[int] = None
    adresse: Optional[str] = None
    num_securite_sociale: int
    
class SalariesResponse(SalariesBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
    
class ProjetsBase(BaseModel):
    nom: str
    client_id: int
    marge_cible: Optional[float] = None
    salarie_id: Optional[int] = None
    tjm: Optional[int] = None
    status_paiement: Optional[str] = None
    champ_remarque: Optional[str] = None
    
class ClientResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)
class ProjetResponse(ProjetsBase):
    id: int
    salarie: Optional[SalariesResponse] = None
    client: Optional[ClientResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    
    
class HistoriqueSalarieCreate(BaseModel):
    salarie_id: int
    date: str                # ex: "2026-05"
    joursTravailles: float
    paye: int
    tjm: float
    salaireBrut: float
    netAvantImpot: float
    netPayer: float
    chargesPatronales: float
    facture: int
    repasRestaurant: float
    totalCotisationsSalariales: float
    totalNoteFrais: float
    totalNoteKilometrique: float
    totalePercu: float
    totaleFacture: float
    salaireNetHorsRepas: float
    projet_id: int
    rentabilite: float
    
class HistoriqueSalarieResponse(HistoriqueSalarieCreate):
    id: int
    salarie: SalariesResponse 
    projet_sal: ProjetResponse
    model_config = ConfigDict(from_attributes=True)
    

class RoleBase(BaseModel):
    name:str
    description:str
class RoleResponse(RoleBase):
    id:int
    model_config = ConfigDict(from_attributes=True)



class HistoryMessage(BaseModel):
      role: str        # "user" ou "assistant"
      content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[HistoryMessage]] = []
    forced_lang: Optional[str] = None


class DashboardKpiCard(BaseModel):
    total_clients: int
    total_prospects: int
    total_salaries: int
    total_projects: int
    total_roles: int
    total_operations: int
    total_factures: int
    factures_payees: int
    factures_impayees: int
    factures_en_retard: int
    avg_tjm: float
    marge_cible_moyenne: float


class DashboardFinancialSummary(BaseModel):
    chiffre_affaires_ttc: float
    chiffre_affaires_ht: float
    tva: float
    montant_paye: float
    reste_a_payer: float
    total_facture_historique: float
    total_cout_historique: float
    rentabilite_totale: float
    taux_marge: float


class DashboardEvolutionPoint(BaseModel):
    periode: str
    chiffre_affaires: float
    cout: float
    rentabilite: float
    taux_marge: float
    operations: int


class DashboardProjectPerformance(BaseModel):
    projet_id: int
    projet_nom: str
    client_id: Optional[int] = None
    client_nom: Optional[str] = None
    salarie_id: Optional[int] = None
    salarie_nom: Optional[str] = None
    tjm: float
    marge_cible: float
    chiffre_affaires: float
    cout: float
    rentabilite: float
    taux_marge: float
    jours_travailles: float
    operations: int


class DashboardSalariePerformance(BaseModel):
    salarie_id: int
    salarie_nom: str
    email: Optional[str] = None
    role: Optional[str] = None
    tjm: float
    chiffre_affaires: float
    cout: float
    rentabilite: float
    taux_marge: float
    jours_travailles: float
    projets: int
    operations: int


class DashboardClientPerformance(BaseModel):
    client_id: int
    client_nom: str
    code_client: Optional[str] = None
    type_client: Optional[str] = None
    chiffre_affaires_ttc: float
    montant_paye: float
    reste_a_payer: float
    factures: int
    factures_payees: int
    projets: int


class DashboardAlert(BaseModel):
    type: str
    niveau: str
    titre: str
    message: str
    valeur: Optional[float] = None
    entity_id: Optional[int] = None
    entity_nom: Optional[str] = None


class DashboardGlobalResponse(BaseModel):
    periode: str
    date_generation: datetime
    kpis: DashboardKpiCard
    finances: DashboardFinancialSummary
    evolution_mensuelle: List[DashboardEvolutionPoint]
    top_projets: List[DashboardProjectPerformance]
    top_salaries: List[DashboardSalariePerformance]
    top_clients: List[DashboardClientPerformance]
    alertes: List[DashboardAlert]
