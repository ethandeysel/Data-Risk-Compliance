from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from src.database.base import Base
from .associations import obligation_data_types


class DataType(Base):

    __tablename__ = "data_types"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), unique=True)

    obligations = relationship(
        "Obligation",
        secondary=obligation_data_types,
        back_populates="data_types",
    )