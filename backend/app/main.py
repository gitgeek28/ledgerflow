import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, dashboard, health, invoices, policies, queue, reference, runs, samples
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    workers = []
    if settings.embedded_worker:
        from app.workers.runner import start_background_workers
        workers = start_background_workers(settings.worker_concurrency)
        log.info("embedded_workers_started", count=len(workers))
    yield
    for w in workers:
        w.stop.set()


app = FastAPI(title="LedgerFlow API", version="1.0.0", lifespan=lifespan, docs_url="/api/docs",
              openapi_url="/api/openapi.json", redoc_url=None,
              description="Intelligent accounts-payable operations: invoice PDF to explainable AP decision.")
install_error_handlers(app)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "Content-Disposition"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    if not request.url.path.endswith("/stream"):
        log.info("request", method=request.method, path=request.url.path, status=response.status_code,
                 ms=int((time.perf_counter() - started) * 1000))
    structlog.contextvars.clear_contextvars()
    return response


for r in (health.router, auth.router, invoices.router, runs.router, reference.router, queue.router, audit.router,
          policies.router, dashboard.router, samples.router):
    app.include_router(r, prefix="/api")
