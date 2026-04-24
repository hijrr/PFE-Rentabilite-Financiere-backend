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
    client: str
    marge_cible: Optional[float] = None
    salarie_id: Optional[int] = None
    tjm: Optional[int] = None
    status_paiement: Optional[str] = None
    champ_remarque: Optional[str] = None
    
    
class ProjetResponse(ProjetsBase):
    id: int
    salarie: Optional[SalariesResponse] = None
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
