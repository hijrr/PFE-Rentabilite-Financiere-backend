from sqlalchemy.orm import relationship

from .database import Base
from sqlalchemy import BIGINT, TIMESTAMP, BigInteger, Column, Enum, Float, ForeignKey,Integer,String, Text,text
import enum
NOW = text('now()')
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
                        nullable=False, server_default=NOW)
    
    
class Salaries(Base):
    __tablename__ = "salaries"
    id = Column(Integer, primary_key=True, nullable=False)
    username = Column(String, nullable=False, unique=True)
    email=Column(String, nullable=False, unique=True)
    role=Column(String, nullable=False)
    tjm=Column(Integer, nullable=True)
    adresse=Column(String, nullable=True)
    date_entree=Column(TIMESTAMP(timezone=True), nullable=False, server_default=NOW)
    num_securite_sociale=Column(BIGINT, nullable=False)
    projets = relationship("Projet", back_populates="salarie",cascade="all, delete", passive_deletes=True)
    historiques = relationship(
    "HistoriqueSalarie",
    back_populates="salarie",
    cascade="all, delete",
    passive_deletes=True
)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=NOW)
    

class Projet(Base):
    __tablename__ = "projet"
    id = Column(Integer, primary_key=True, nullable=False)
    nom = Column(String, nullable=False, unique=False)
    client=Column(String, nullable=False)
    marge_cible = Column(Float, nullable=True)
    tjm=Column(Integer, nullable=True)
    champ_remarque=Column(String, nullable=True)
    status_paiement=Column(String, nullable=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id",ondelete="CASCADE"),nullable=False)
    salarie = relationship("Salaries",back_populates="projets")
    historiques_projet = relationship("HistoriqueSalarie", back_populates="projet_sal", cascade="all, delete",passive_deletes=True)
    created_at = Column(TIMESTAMP(timezone=True),nullable=False, server_default=NOW)
    
class HistoriqueSalarie(Base):
    __tablename__ = "historique_salarie"
    id = Column(Integer, primary_key=True, index=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id",ondelete="CASCADE"), nullable=False)
    salarie = relationship("Salaries", back_populates="historiques")
    projet_id = Column(Integer, ForeignKey("projet.id",ondelete="CASCADE"), nullable=False)
    projet_sal = relationship("Projet", back_populates="historiques_projet")
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
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=NOW)
    
class Client(Base):
    __tablename__ = "Clients"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    name            = Column(String(128),  nullable=False, comment="Nom du client")
    code_client     = Column(String(24),   nullable=True,  comment="Code client unique")
    client          = Column(String(1),    nullable=True,  comment="1=Client, 2=Prospect")
    logo            = Column(String(255),  nullable=True,  comment="Nom du fichier logo")
    email           = Column(String(128),  nullable=True)
    phone           = Column(String(20),   nullable=True,  comment="Téléphone")
    fax             = Column(String(20),   nullable=True)
    url             = Column(String(255),  nullable=True,  comment="Site web")
    address         = Column(Text,         nullable=True)
    zip             = Column(String(25),   nullable=True,  comment="Code postal")
    town            = Column(String(50),   nullable=True,  comment="Ville")
    country_code    = Column(String(2),    nullable=True,  comment="Code ISO pays (FR, GB…)")
    idprof1         = Column(String(20),   nullable=True,  comment="SIRET (14 chiffres)")
    idprof2         = Column(String(20),   nullable=True,  comment="SIREN")
    idprof3         = Column(String(20),   nullable=True,  comment="Code NAF / APE")
    tva_intra       = Column(String(20),   nullable=True,  comment="N° TVA intracommunautaire")
    forme_juridique = Column(String(100),  nullable=True,  comment="SAS, SARL, SA…")
    capital         = Column(Float,        nullable=True,  comment="Capital social en €")
    effectif        = Column(String(10),   nullable=True,  comment="Tranche effectif")
    date_creation     = Column(BigInteger, nullable=True)
    date_modification = Column(BigInteger, nullable=True)
    factures = relationship("Facture", back_populates="client_obj",
                            foreign_keys="Facture.socid")
    
class Facture(Base):
    __tablename__ = "factures"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    ref             = Column(String(30),  nullable=False, unique=True,
                             comment="Référence facture (ex: FA2024-0001)")
    socid           = Column(Integer, ForeignKey("Clients.id"),
                             nullable=False, comment="ID du client (llx_societe)")
    date                    = Column(BigInteger, nullable=True, comment="Date d'émission")
    date_lim_reglement      = Column(BigInteger, nullable=True, comment="Date d'échéance")
    date_creation           = Column(BigInteger, nullable=True, comment="Date de création")
    date_validation         = Column(BigInteger, nullable=True, comment="Date de validation")
    total_ht        = Column(Float, nullable=True, default=0.0, comment="Montant HT")
    total_tva       = Column(Float, nullable=True, default=0.0, comment="Montant TVA")
    total_ttc       = Column(Float, nullable=True, default=0.0, comment="Montant TTC")
    sumpayed        = Column(Float, nullable=True, default=0.0, comment="Déjà payé")
    jours_travailles=Column(Integer,nullable=True,default=0)
    tjm=Column(Float,nullable=True,default=0.0)
    resteapayer     = Column(Float, nullable=True, default=0.0, comment="Reste à payer")
    paye            = Column(String(1),  nullable=True,
                             comment="0=Non payée, 1=Payée")
    statut          = Column(String(1),  nullable=True,
                             comment="0=Brouillon, 1=Validée/En attente, 2=Clôturée")
    online_payment_url = Column(String(255), nullable=True,
                                comment="URL de paiement en ligne")
    client_obj = relationship("Client", back_populates="factures",
                              foreign_keys=[socid])



class Role(Base):
    __tablename__ = "role"
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False, unique=True)
    description=Column(String,nullable=True)
    created_at=Column(TIMESTAMP(timezone=True), nullable=False, server_default=NOW)