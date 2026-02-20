from fastapi import APIRouter,FastAPI, HTTPException,Depends
from .. import schemas,utils,oauth2
from sqlalchemy.orm import Session
from ..config import settings
from ldap3 import Server, Connection, NTLM
from ..database import get_db
from ..models import User, UserRole
from app import models

router = APIRouter(tags=["Auth"])

AD_SERVER = f'ldap://{settings.AD_SERVER}'
AD_DOMAIN = settings.AD_DOMAIN


@router.post("/login")
def login(data: schemas.LoginRequest,db: Session = Depends(get_db)):

    user = f"{AD_DOMAIN}\\{data.username}"

    server = Server(AD_SERVER)
    conn = Connection(server, user=user, password=data.password, authentication=NTLM)
    if not conn.bind():
        raise HTTPException(status_code=401, detail="Nom d'utilisateur ou mot de passe invalide")
    conn.search(
    search_base="dc=elzei,dc=local",   # ton domaine
    search_filter=f"(sAMAccountName={data.username})",
    attributes=['memberOf']            # ca retourne les groupes
)
    groups = conn.entries[0].memberOf
    print(groups)
    role = UserRole.gestionnaire_financier 
    for g in groups:
      g_upper = str(g).upper()
      if "ADMIN_TEAM" in g_upper:
            role = UserRole.admin
            break
      elif "FINANCE_TEAM" in g_upper:
            role = UserRole.gestionnaire_financier
            break 

    user_db = db.query(User).filter(User.username == data.username).first()
    if not user_db:
         hashed_password=utils.hash(data.password)
         user_db = User(username=data.username, password=hashed_password, role=role)
         db.add(user_db)
         db.commit()
         db.refresh(user_db)
    else:
        if user_db.role != role:
            user_db.role = role
            db.commit()
              
    token_data = {"user_id": user_db.id, "role": user_db.role.value}
    print("Token Data:", token_data) 
    access_token = oauth2.create_access_token(token_data)
    return {"access_token": access_token, "token_type": "bearer"}         