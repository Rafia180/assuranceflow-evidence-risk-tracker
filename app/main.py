"""AssuranceFlow - a fictional cyber compliance evidence & risk tracker (learning project)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.routes import assurance, dashboard, registers
from app.seed import seed_if_empty
from app.templating import BASE_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        seed_if_empty(session)
    yield


app = FastAPI(title="AssuranceFlow", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(dashboard.router)
app.include_router(registers.router)
app.include_router(assurance.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": "AssuranceFlow"}
