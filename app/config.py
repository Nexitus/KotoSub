from typing import Optional
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None

    # App Settings
    TEMP_DIR: str = os.path.join(os.getcwd(), "temp")
    OUTPUT_DIR: str = os.path.join(os.getcwd(), "output")
    MAX_FILE_SIZE_MB: int = 2000
    
    # Model Configurations
    WHISPER_MODEL: str = "whisper-1"
    LLM_MODEL: str = "gpt-4-turbo-preview"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Ensure directories exist
os.makedirs(settings.TEMP_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
