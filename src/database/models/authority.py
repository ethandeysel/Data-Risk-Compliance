from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from src.database.base import Base


class Authority(Base):

    __tablename__ = "authorities"

    id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=False)

    authority_type = Column(String(100))
    # Regulator
    # Ministry
    # Court
    # Government Department
    # Standards Body

    website = Column(String(500))

    country_id = Column(Integer, ForeignKey("countries.id"))

    country = relationship("Country")