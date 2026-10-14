"""RailMitra FastAPI application shell.

Smart Railway Seat Exchange & Family Seating System.
Prototype boundary: Uses simulated reservation dataset.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.config import settings
from app.database import AsyncSessionLocal, close_db, get_db, init_db
from app.errors import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.schemas import DemoResetResponse, HealthResponse
from app.seed import reset_database, seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initialize schema and seed database on startup."""
    # 1. Initialize tables
    await init_db()

    # 2. Seed simulated reservation dataset idempotently
    async with AsyncSessionLocal() as session:
        await seed_database(session)

    yield

    # Shutdown
    await close_db()


app = FastAPI(
    title="RailMitra API",
    version=settings.APP_VERSION,
    description=(
        "Smart Railway Seat Exchange & Family Seating System (Hackathon MVP).\n\n"
        "**PROTOTYPE DISCLAIMER:** Prototype using a simulated reservation dataset. "
        "Not the official Indian Railways reservation chart or database. "
        "Official use would require authorization from Indian Railways."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers returning standardized { "detail": ..., "code": ... }
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API Routers
from app.routers import (
    auth,
    consent,
    groups,
    journey,
    matching,
    notifications,
    requests,
    simulation,
    slip,
    tte,
    websocket,
)

app.include_router(journey.router)
app.include_router(auth.router)
app.include_router(matching.router)
app.include_router(requests.router)
app.include_router(consent.router)
app.include_router(groups.router)
app.include_router(tte.router)
app.include_router(notifications.router)
app.include_router(slip.router)
app.include_router(simulation.router)
app.include_router(websocket.router)


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve landing index page."""
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint verifying database connectivity and configuration."""
    db_ok = False
    try:
        res = await db.execute(text("SELECT 1"))
        db_ok = res.scalar() == 1
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        demo_mode=settings.DEMO_MODE,
        database_connected=db_ok,
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/api/demo/reset", response_model=DemoResetResponse, tags=["Demo"])
async def demo_reset(db: AsyncSession = Depends(get_db)):
    """Reset simulated dataset back to the baseline state with worked examples."""
    from app.services.expiry import reset_train_positions
    reset_train_positions()
    stats = await reset_database(db)
    return DemoResetResponse(
        message=stats.get("message", "Database reset complete."),
        passengers_count=stats.get("passengers_count", 0),
        trains_count=stats.get("trains_count", 0),
        groups_count=stats.get("groups_count", 0),
    )
