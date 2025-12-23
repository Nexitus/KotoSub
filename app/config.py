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
    # Where to store downloaded models
    MODELS_DIR: str = os.path.join(os.getcwd(), "models")
    MAX_FILE_SIZE_MB: int = 2000
    
    # Model Configurations
    WHISPER_MODEL: str = "whisper-1"
    LLM_MODEL: str = "gpt-4-turbo-preview"

    # Local Processing Settings
    TRANSCRIPTION_PROVIDER: str = "openai" # "openai" or "local"
    TRANSLATION_PROVIDER: str = "openai" # "openai" or "local"
    
    LOCAL_WHISPER_MODEL: str = "medium" # tiny, base, small, medium, large-v3
    LOCAL_LLM_MODEL: str = "TheBloke/Mistral-7B-Instruct-v0.2-GGUF" # HuggingFace repo or local path
    LOCAL_LLM_FILE: Optional[str] = "mistral-7b-instruct-v0.2.Q4_K_M.gguf" # Specific file in repo

    USE_GPU_ENCODING: bool = False
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Ensure directories exist
os.makedirs(settings.TEMP_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.MODELS_DIR, exist_ok=True)
