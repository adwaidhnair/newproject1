import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./erp_intel.db")
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg://", 1
    ).replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
if DATABASE_URL.startswith("sqlite:///") and DATABASE_URL != "sqlite:///:memory:":
    database_path = DATABASE_URL.removeprefix("sqlite:///").split("?", 1)[0]
    resolved_path = Path(database_path)
    if not resolved_path.is_absolute():
        resolved_path = Path(__file__).resolve().parents[2] / resolved_path
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{resolved_path.as_posix()}"
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    **(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
        }
        if not DATABASE_URL.startswith("sqlite")
        else {}
    ),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
