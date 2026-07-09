from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from src.database.base import Base


class DocumentNode(Base):

    __tablename__ = "document_nodes"

    id = Column(Integer, primary_key=True)

    act_id = Column(Integer, ForeignKey("acts.id"), nullable=False)

    parent_id = Column(Integer, ForeignKey("document_nodes.id"))

    node_type = Column(String(50), nullable=False)
    # Act
    # Chapter
    # Part
    # Division
    # Section
    # Subsection
    # Schedule
    # Annexure

    identifier = Column(String(100))
    # Section 72
    # Chapter 3
    # Part IV

    title = Column(String(500))

    page_start = Column(Integer)

    page_end = Column(Integer)

    raw_text = Column(Text)

    clean_text = Column(Text)

    act = relationship(
        "Act",
        back_populates="nodes",
    )

    parent = relationship(
        "DocumentNode",
        remote_side=[id],
        back_populates="children",
    )

    children = relationship(
        "DocumentNode",
        back_populates="parent",
    )

    obligations = relationship(
        "Obligation",
        back_populates="node",
    )

    sources = relationship(
        "Source",
        back_populates="node",
    )