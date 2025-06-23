from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0" 
    port: int = 8000
    debug: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # CORS - 테스트용으로 모든 오리진 허용
    cors_allow_all: bool = True
    
    class Config:
        env_file = ".env"


settings = Settings()