from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from src.database.base import Base


class Act(Base):

    __tablename__ = "acts"

    id = Column(Integer, primary_key=True)

    title = Column(String(500), nullable=False)

    year = Column(Integer)

    document_type = Column(String(100))

    status = Column(String(50))

    official_url = Column(String(1000))

    country_id = Column(Integer, ForeignKey("countries.id"))

    regulator_id = Column(Integer, ForeignKey("regulators.id"))

    country = relationship("Country", back_populates="acts")

    regulator = relationship("Regulator", back_populates="acts")

    nodes = relationship(
    "DocumentNode",
    back_populates="act",
    cascade="all, delete-orphan",
    )

    effective_date = Column(Date)

    publication_date = Column(Date)

    last_updated = Column(Date)

    version = Column(String(50))