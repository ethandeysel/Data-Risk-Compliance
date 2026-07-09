from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from src.database.base import Base


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), nullable=False, unique=True)

    iso_code = Column(String(3), unique=True)

    acts = relationship("Act", back_populates="country")

    regulators = relationship("Regulator", back_populates="country")