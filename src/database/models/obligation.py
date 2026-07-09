from sqlalchemy import Column, Integer, Text, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship

from src.database.base import Base
from .associations import (
    obligation_topics,
    obligation_sectors,
    obligation_data_types,
)


class Obligation(Base):

    __tablename__ = "obligations"

    id = Column(Integer, primary_key=True)

    node_id = Column(
        Integer,
        ForeignKey("document_nodes.id"),
    )

    authority_id = Column(
        Integer,
        ForeignKey("authorities.id"),
    )
    summary = Column(Text)

    mandatory = Column(Boolean)

    confidence = Column(Float)

    penalty = Column(Text)

    notes = Column(Text)

    node = relationship(
        "DocumentNode",
        back_populates="obligations",
    )
    
    topics = relationship(
        "Topic",
        secondary=obligation_topics,
        back_populates="obligations",
    )

    sectors = relationship(
        "Sector",
        secondary=obligation_sectors,
        back_populates="obligations",
    )

    data_types = relationship(
        "DataType",
        secondary=obligation_data_types,
        back_populates="obligations",
    )