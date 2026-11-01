import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import engine, Base
import backend.app.models.models  # Ensure models are imported for table creation
from backend.app.api import (
    documents,
    analysis,
    sources,
    suggestions,
    revisions,
    validation,
    export,
    detector,
    evidence,
    settings as app_settings,
    auth,
    payments,
    upload_gate,
    admin,
)

# Create tables in dev/test mode; migrations manage production
if settings.ENVIRONMENT != "production":
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Locally runnable academic manuscript integrity, originality analysis, and preservation studio.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS setup with strict allowlist
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Register routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(payments.router, prefix=settings.API_PREFIX)
app.include_router(upload_gate.router, prefix=settings.API_PREFIX)
app.include_router(admin.router, prefix=settings.API_PREFIX)
app.include_router(documents.router, prefix=settings.API_PREFIX)
app.include_router(analysis.router, prefix=settings.API_PREFIX)
app.include_router(analysis.jobs_router, prefix=settings.API_PREFIX)
app.include_router(analysis.findings_router, prefix=settings.API_PREFIX)
app.include_router(sources.router, prefix=settings.API_PREFIX)
app.include_router(suggestions.router, prefix=settings.API_PREFIX)
app.include_router(revisions.router, prefix=settings.API_PREFIX)
app.include_router(validation.router, prefix=settings.API_PREFIX)
app.include_router(export.router, prefix=settings.API_PREFIX)
app.include_router(detector.router, prefix=settings.API_PREFIX)
app.include_router(evidence.router, prefix=settings.API_PREFIX)
app.include_router(app_settings.router, prefix=settings.API_PREFIX)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "default_provider": settings.DEFAULT_LLM_PROVIDER,
        "database": "sqlite_ready",
        "libreoffice": os.path.exists(settings.LIBREOFFICE_PATH)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
