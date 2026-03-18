from .database import Base
from sqlalchemy import TIMESTAMP, Column, Enum, ForeignKey,Integer,String,Boolean, text
import enum

class UserRole(enum.Enum):
    admin = "admin"
    gestionnaire_financier = "gestionnaire_financier"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, nullable=False)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    role = Column(Enum(UserRole),default=UserRole.gestionnaire_financier,
        nullable=False
    )
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    
    
class Salaries(Base):
    __tablename__ = "salaries"
    id = Column(Integer, primary_key=True, nullable=False)
    username = Column(String, nullable=False, unique=True)
    role=Column(String, nullable=False)
    projet=Column(String, nullable=True)
    tjm=Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    

class Projet(Base):
    __tablename__ = "projet"
    id = Column(Integer, primary_key=True, nullable=False)
    nom = Column(String, nullable=False, unique=False)
    client=Column(String, nullable=False)
    jours_travailles=Column(Integer, nullable=True)
    tjm=Column(Integer, nullable=True)
    status_paiement=Column(String, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True),nullable=False, server_default=text('now()'))