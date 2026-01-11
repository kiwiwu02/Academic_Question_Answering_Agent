# backend/app/main.py
from fastapi import FastAPI
from contextlib import contextmanager, asynccontextmanager
import logging
from .database import create_tables
from .api import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the application...")
    create_tables()
    yield
    logger.info("Shutting down the application...")

app=FastAPI(
    title="Academic Research Agent",
    description="An AI-powered agent to assist with academic research tasks.",
    version="1.0.0",
    lifespan=lifespan   # 注册lifespan
)

app.include_router(api_router)  