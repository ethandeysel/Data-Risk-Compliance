from sqlalchemy import create_engine

from src.database.base import Base

# Import ALL models
from src.database.models import *

DATABASE_URL = "sqlite:///database/compliance.db"

engine = create_engine(DATABASE_URL)

Base.metadata.create_all(engine)

print("Database created.")