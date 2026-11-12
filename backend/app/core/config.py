from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_name: str = "LedgerFlow"
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://ledgerflow:ledgerflow@localhost:5432/ledgerflow"
    # Direct (non-pooled) URL for schema migrations when DATABASE_URL goes through a pooler such as Neon's.
    database_url_unpooled: str | None = None
    storage_backend: str = "local"  # "local" (STORAGE_DIR) | "db" (stored_documents table)
    storage_dir: Path = BACKEND_DIR / "storage"
    max_upload_mb: int = 20
    max_pages: int = 50

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    secret_key: str = "change-me-local-demo-secret"
    # Key for bank-account fingerprints. Deliberately separate from SECRET_KEY: rotating the session secret
    # must not invalidate stored fingerprints (that would raise false bank-change alarms). Rotating THIS key
    # requires re-fingerprinting the vendor master.
    fingerprint_key: str = "ledgerflow-demo-fingerprint-key"
    demo_password: str = "ledgerflow-demo"
    session_ttl_hours: int = 12
    cookie_secure: bool = False

    # OCR
    tesseract_cmd: str | None = None
    ocr_dpi: int = 300
    ocr_min_chars_per_page: int = 40

    # Local LLM (Ollama) — optional, free, runs on this machine
    llm_provider: str = "ollama"  # "ollama" | "none"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_s: float = 90.0

    # Worker
    embedded_worker: bool = False
    worker_concurrency: int = 2
    worker_poll_interval_s: float = 0.5
    job_lease_seconds: int = 120
    job_max_attempts: int = 3

    # Optional, documented demo pacing between stages (0 = off). Never counted in stage durations.
    demo_stage_pacing_ms: int = 0

    # The buyer organisation (fictional) — used to tell "bill to" identifiers apart from the supplier's.
    buyer_name: str = "Kestrel Components Pvt Ltd"
    buyer_gstin: str = "27AAGCK4821M1Z8"

    @field_validator("database_url", "database_url_unpooled")
    @classmethod
    def _psycopg_driver(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Hosting providers hand out postgres:// URLs; SQLAlchemy needs the explicit psycopg driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
