"""Database connection. SQLite keeps the project simple and portable."""
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./assuranceflow.db"

# check_same_thread=False lets FastAPI use the connection across threads.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: one database session per request."""
    with Session(engine) as session:
        yield session
