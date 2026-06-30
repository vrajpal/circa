from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, schedule, odds, picks, consensus, team_stats

# Schema is owned by Alembic — run `alembic upgrade head` to provision/migrate.
# (This module used to call Base.metadata.create_all on import, which raced
# ahead of migrations and created tables Alembic didn't know about.)

app = FastAPI(title="Circa Contest Planner", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(schedule.router)
app.include_router(odds.router)
app.include_router(picks.router)
app.include_router(consensus.router)
app.include_router(team_stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
