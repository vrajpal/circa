import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.logging_config import setup_logging, get_logger
from app.routers import auth, schedule, odds, picks, consensus, team_stats

setup_logging()
logger = get_logger(__name__)

# Create tables on startup (Alembic used for production migrations)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Circa Contest Planner", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


app.include_router(auth.router)
app.include_router(schedule.router)
app.include_router(odds.router)
app.include_router(picks.router)
app.include_router(consensus.router)
app.include_router(team_stats.router)

logger.info("Circa Contest Planner started")


@app.get("/api/health")
def health():
    return {"status": "ok"}
