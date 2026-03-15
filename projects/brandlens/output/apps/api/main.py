import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
import logging
from core.config import settings
from api.companies import router as companies_router

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

app = FastAPI(title="BrandLens API", version="1.0.0")

# Setup CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Add production frontend URL here later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up BrandLens API", environment=settings.ENVIRONMENT, port=settings.PORT)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    import uvicorn
    # When running directly, use settings port or fallback to 8000
    port = int(os.environ.get("PORT", settings.PORT))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=(settings.ENVIRONMENT == "development"))
