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