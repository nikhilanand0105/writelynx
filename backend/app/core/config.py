import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Writelynx"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_PREFIX: str = "/api"
    DATABASE_URL: str = f"sqlite:///{STORAGE_DIR}/manuscript_studio.db"
    
    # File limits and storage
    STORAGE_DIR: Path = STORAGE_DIR
    DOCUMENTS_DIR: Path = STORAGE_DIR / "documents"
    QUARANTINE_DIR: Path = STORAGE_DIR / "quarantine"
    SOURCES_DIR: Path = STORAGE_DIR / "sources"
    EXPORTS_DIR: Path = STORAGE_DIR / "exports"
    REPORTS_DIR: Path = STORAGE_DIR / "reports"
    MAX_FILE_SIZE_MB: int = 50
    
    # Auth & OAuth Settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "mock-google-client-id")
    TEST_MODE_MOCK_AUTH: bool = os.getenv("TEST_MODE_MOCK_AUTH", "1").lower() in ("1", "true", "yes")
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
    ALLOWED_STUDENT_DOMAIN: str = "vitstudent.ac.in"
    ADMIN_EMAILS: list[str] = [
        e.strip() for e in os.getenv("ADMIN_EMAILS", "admin@vitstudent.ac.in,system@writelynx.internal").split(",") if e.strip()
    ]
    
    # Razorpay Payment Settings (Integer Paise: 1 INR = 100 paise)
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "rzp_test_writelynx")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "mock_razorpay_secret")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "mock_webhook_secret")
    
    # Pricing tiers configuration (price in paise, budgets in paise)
    PLAN_CONFIGS: dict = {
        "basic": {
            "name": "Basic",
            "price_paise": 2000,       # ₹20
            "max_pages": 4,
            "max_characters": 15000,
            "max_file_size_mb": 10,
            "ai_budget_paise": 400,    # ₹4
        },
        "standard": {
            "name": "Standard",
            "price_paise": 5000,       # ₹50
            "max_pages": 20,
            "max_characters": 65000,
            "max_file_size_mb": 20,
            "ai_budget_paise": 900,    # ₹9
        },
        "extended": {
            "name": "Extended",
            "price_paise": 10000,      # ₹100
            "max_pages": 50,
            "max_characters": 160000,
            "max_file_size_mb": 30,
            "ai_budget_paise": 2400,   # ₹24
        },
    }
    
    # Operating Modes
    OPERATING_MODES: dict = {
        "proofreading": "Proofreading and clarity",
        "academic_revision": "Natural academic revision",
        "evidence_review": "Research and evidence-grounded review",
    }
    
    # LibreOffice binary path for headless PDF conversion
    LIBREOFFICE_PATH: str = os.getenv(
        "LIBREOFFICE_PATH",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    )
    
    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "no_llm"  # no_llm | ollama | openai | gemini | custom
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    CUSTOM_ENDPOINT: str = os.getenv("CUSTOM_ENDPOINT", "")
    CUSTOM_API_KEY: str = os.getenv("CUSTOM_API_KEY", "")
    
    # Telemetry and privacy
    OFFLINE_ONLY: bool = True  # Strict local privacy by default
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://writelynx.pages.dev",
        "https://writelynx.in",
        "https://api.writelynx.in",
    ]
    MAX_PDF_PAGES: int = 500
    MAX_EVIDENCE_TEXT_CHARS: int = 2_000_000
    
    # Document Retention Policy (Phase 18)
    DOCUMENT_RETENTION_DAYS: int = int(os.getenv("DOCUMENT_RETENTION_DAYS", "7"))  # 7 days for completed outputs
    ABANDONED_UPLOAD_HOURS: int = int(os.getenv("ABANDONED_UPLOAD_HOURS", "1"))    # 1 hour for abandoned uploads
    QUARANTINE_PURGE_HOURS: int = int(os.getenv("QUARANTINE_PURGE_HOURS", "2"))    # 2 hours for failed quarantine files

    @model_validator(mode="after")
    def derive_storage_paths(self):
        for name, child in [("DOCUMENTS_DIR", "documents"), ("SOURCES_DIR", "sources"),
                            ("EXPORTS_DIR", "exports"), ("REPORTS_DIR", "reports")]:
            if name not in self.model_fields_set:
                setattr(self, name, self.STORAGE_DIR / child)
        if "DATABASE_URL" not in self.model_fields_set:
            self.DATABASE_URL = f"sqlite:///{self.STORAGE_DIR}/manuscript_studio.db"

        # Production safety validations
        if self.ENVIRONMENT == "production":
            if self.TEST_MODE_MOCK_AUTH:
                raise ValueError("SECURITY BLOCKER: TEST_MODE_MOCK_AUTH must be disabled in production.")
            if not self.GOOGLE_CLIENT_ID or self.GOOGLE_CLIENT_ID == "mock-google-client-id":
                raise ValueError("SECURITY BLOCKER: Real GOOGLE_CLIENT_ID is required in production.")
            if not self.RAZORPAY_KEY_SECRET or self.RAZORPAY_KEY_SECRET == "mock_razorpay_secret":
                raise ValueError("SECURITY BLOCKER: Production RAZORPAY_KEY_SECRET must be configured.")

        # Add custom origins if provided via environment
        env_origins = os.getenv("ALLOWED_ORIGINS", "")
        if env_origins:
            for origin in env_origins.split(","):
                clean = origin.strip()
                if clean and clean not in self.ALLOWED_ORIGINS:
                    self.ALLOWED_ORIGINS.append(clean)

        return self
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Ensure directories exist
for folder in [
    settings.STORAGE_DIR,
    settings.DOCUMENTS_DIR,
    settings.QUARANTINE_DIR,
    settings.SOURCES_DIR,
    settings.EXPORTS_DIR,
    settings.REPORTS_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)
