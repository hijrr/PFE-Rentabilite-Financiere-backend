from sqlalchemy.orm import relationship

from .database import Base
from sqlalchemy import BIGINT, TIMESTAMP, Column, Enum, Float, ForeignKey,Integer,String,Boolean, text
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
    email=Column(String, nullable=False, unique=True)
    role=Column(String, nullable=False)
    tjm=Column(Integer, nullable=True)
    adresse=Column(String, nullable=True)
    date_entree=Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    num_securite_sociale=Column(BIGINT, nullable=False)
    projets = relationship("Projet", back_populates="salarie")
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    

class Projet(Base):
    __tablename__ = "projet"
    id = Column(Integer, primary_key=True, nullable=False)
    nom = Column(String, nullable=False, unique=False)
    client=Column(String, nullable=False)
    marge_cible = Column(Float, nullable=True)
    tjm=Column(Integer, nullable=True)
    champ_remarque=Column(String, nullable=True)
    status_paiement=Column(String, nullable=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id"))
    salarie = relationship("Salaries",back_populates="projets")
    created_at = Column(TIMESTAMP(timezone=True),nullable=False, server_default=text('now()'))
    
class HistoriqueSalarie(Base):
    __tablename__ = "historique_salarie"

    id = Column(Integer, primary_key=True, index=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    salarie = relationship("Salaries", backref="historiques")
    date = Column(String)
    joursTravailles = Column(Float)
    paye = Column(Integer)
    tjm = Column(Float)
    salaireBrut = Column(Float)
    netAvantImpot = Column(Float)
    netPayer = Column(Float)
    chargesPatronales = Column(Float)
    facture = Column(Integer)
    repasRestaurant = Column(Float)
    totalCotisationsSalariales = Column(Float)
    totalNoteFrais = Column(Float)
    totalNoteKilometrique = Column(Float)
    totalePercu = Column(Float)
    totaleFacture = Column(Float)
    salaireNetHorsRepas = Column(Float)
    rentabilite = Column(Float)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))