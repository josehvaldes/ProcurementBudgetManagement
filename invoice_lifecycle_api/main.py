import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from invoice_lifecycle_api.api import budget, health, intake
from invoice_lifecycle_api.application.interfaces.di_container import close_all_services
from shared.utils.logging_config import get_logger, setup_logging
from shared.config.settings import settings

setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )

logger = get_logger(__name__)

print(f"Loading environment settings for: {settings.environment}")

async def warmup_services():
    """Warm up any necessary services before the application starts."""
    logger.info("Warming up services...")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Invoice Lifecycle API...")
    logger.info(f"API Title: {settings.api_title} Version: {settings.api_version}")
    
    # Warmup services
    await warmup_services()
    
    yield
    
    # Shutdown
    await close_all_services()
    logger.info("Shutting down Invoice Lifecycle API...")


app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    debug=settings.debug,
    lifespan=lifespan
)

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    logger.warning(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url.path} "
        f"Status: {response.status_code} "
        f"Duration: {process_time:.3f}s"
    )
    return response


# CORS settings
origins = ["http://localhost:5173", 
           "http://localhost:8080",
           #"http://???:8080" # internal access from container
           ]  # React dev servers

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(intake.router, prefix="/api/v1/intake", tags=["intake"])
app.include_router(budget.router, prefix="/api/v1/budgets", tags=["budgets"])

def run_production():
    """Entry point for the CLI script."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_production()
