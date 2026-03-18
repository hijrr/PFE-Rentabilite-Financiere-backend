from datetime import datetime
from typing import Optional

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
    role: str
    projet: Optional[str] = None
    tjm: Optional[int] = None
    
    
class SalariesResponse(SalariesBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
    
class ProjetsBase(BaseModel):
    nom: str
    client: str
    jours_travailles: Optional[int] = None
    tjm: Optional[int] = None
    status_paiement: Optional[str] = None
    
    
class ProjetResponse(ProjetsBase):
    id: int
    model_config = ConfigDict(from_attributes=True)