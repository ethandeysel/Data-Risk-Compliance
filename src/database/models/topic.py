from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from src.database.base import Base
from .associations import obligation_topics


class Topic(Base):

    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), unique=True)

    obligations = relationship(
        "Obligation",
        secondary=obligation_topics,
        back_populates="topics",
    )