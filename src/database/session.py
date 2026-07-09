from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import SQLITE_FILE

engine = create_engine(
    f"sqlite:///{SQLITE_FILE}",
    echo=False,
)

SessionLocal = sessionmaker(bind=engine)
