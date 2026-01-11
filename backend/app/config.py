import os
from dotenv import load_dotenv
load_dotenv()
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    #模型设置
    BAI_LIAN_MODEL: str = os.getenv("BAI_LIAN_MODEL", "qwen3-max-preview")
    BAI_LIAN_API_KEY: str = os.getenv("BAI_LIAN_API_KEY", "")
    BAI_LIAN_BASE_URL: str = os.getenv("BAI_LIAN_BASE_URL", "")

    #数据库设置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./academic_research_agent.db")
    
    # 服务器配置
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000").strip('"\' '))
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Agent配置
    agent_temperature: float = float(os.getenv("AGENT_TEMPERATURE", "0.1"))
    agent_max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", "2000"))
    
    class Config:
        env_file = ".env"

settings = Settings()