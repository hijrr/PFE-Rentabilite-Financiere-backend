from datetime import datetime
from typing import Optional

from pydantic import BaseModel

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

    model_config = {
        "from_attributes": True
    }