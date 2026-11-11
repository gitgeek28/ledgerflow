import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://ledgerflow:ledgerflow@localhost:5432/ledgerflow_test")
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="ledgerflow-test-")
os.environ["LLM_PROVIDER"] = "none"
os.environ["EMBEDDED_WORKER"] = "false"
os.environ["DEMO_STAGE_PACING_MS"] = "0"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.core.config import BACKEND_DIR, REPO_DIR  # noqa: E402

FIXTURES = REPO_DIR / "data" / "fixtures" / "pdfs"


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    if not (FIXTURES / "S01_PBI-2026-0981.pdf").exists():
        from app.seed.fixtures import main as generate
        generate()


@pytest.fixture
def db_reset():
    from app.db.session import SessionLocal
    from app.seed.seed import reset, seed
    with SessionLocal() as db:
        reset(db)
        seed(db)
        db.commit()


@pytest.fixture
def db(db_reset):
    from app.db.session import SessionLocal
    with SessionLocal() as session:
        yield session


def drain() -> int:
    """Run queued jobs synchronously with the real worker code."""
    from app.workers.runner import Worker
    w, n = Worker("pytest"), 0
    while w.run_one():
        n += 1
    return n


def pdf(name: str) -> Path:
    matches = list(FIXTURES.glob(f"{name}*.pdf"))
    if not matches:
        raise FileNotFoundError(name)
    return matches[0]


@pytest.fixture
def client(db_reset):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


def login(client, email="aisha.rao@kestrel.example"):
    r = client.post("/api/auth/login", json={"email": email, "password": "ledgerflow-demo"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def upload(client, headers, name: str, filename: str | None = None):
    path = pdf(name) if not isinstance(name, Path) else name
    with open(path, "rb") as fh:
        return client.post("/api/invoices", headers=headers,
                           files={"file": (filename or path.name, fh, "application/pdf")})
