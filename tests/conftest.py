"""Test setup: every test gets a fresh in-memory database, so tests never touch
your real assuranceflow.db file."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app
from app.models import Control, Requirement


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)  # no "with" block -> the seed-data startup hook is not run
    app.dependency_overrides.clear()


@pytest.fixture
def control(session):
    req = Requirement(reference="REQ-T-01", title="Test requirement", category="Access Management",
                      owner="Tester", review_frequency="Quarterly")
    session.add(req)
    session.commit()
    ctrl = Control(requirement_id=req.id, name="Test control", owner="Owner", frequency="Quarterly")
    session.add(ctrl)
    session.commit()
    session.refresh(ctrl)
    return ctrl
