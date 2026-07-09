from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
)

from src.database.base import Base


class DocumentRelationship(Base):

    __tablename__ = "document_relationships"

    id = Column(Integer, primary_key=True)

    source_act_id = Column(
        Integer,
        ForeignKey("acts.id"),
    )

    target_act_id = Column(
        Integer,
        ForeignKey("acts.id"),
    )

    relationship_type = Column(String(100))