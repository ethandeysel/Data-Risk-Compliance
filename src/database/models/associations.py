from sqlalchemy import Table, Column, Integer, ForeignKey

from src.database.base import Base


obligation_topics = Table(
    "obligation_topics",
    Base.metadata,
    Column("obligation_id", ForeignKey("obligations.id"), primary_key=True),
    Column("topic_id", ForeignKey("topics.id"), primary_key=True),
)


obligation_sectors = Table(
    "obligation_sectors",
    Base.metadata,
    Column("obligation_id", ForeignKey("obligations.id"), primary_key=True),
    Column("sector_id", ForeignKey("sectors.id"), primary_key=True),
)


obligation_data_types = Table(
    "obligation_data_types",
    Base.metadata,
    Column("obligation_id", ForeignKey("obligations.id"), primary_key=True),
    Column("data_type_id", ForeignKey("data_types.id"), primary_key=True),
)