from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from src.database.base import Base


class Source(Base):

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)

    node_id = Column(
        Integer,
        ForeignKey("document_nodes.id"),
    )

    page = Column(Integer)

    url = Column(String(1000))

    node = relationship(
        "DocumentNode",
        back_populates="sources",
    )