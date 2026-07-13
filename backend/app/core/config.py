"""
Application settings — reads from .env file via Pydantic Settings.
"""
import json
from typing import Annotated, Any, List
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "yolo"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    STATIC_URL_EXPIRE_SECONDS: int = 3600  # signed /static URLs for <img> tags

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"

    # Ollama (local, no API key required)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # Chat
    CHAT_PROVIDER: str = "openai"
    CHAT_REQUEST_TIMEOUT: int = 60
    CHAT_CONTEXT_MAX_TURNS: int = 10
    CHAT_SYSTEM_PROMPT: str = "You are a concise, helpful assistant for the YOLO System application."
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_CHAT_MODEL: str = "gpt-4.1-mini"

    # Agent (Phase 6A-1)
    # Empty values fall back to CHAT_PROVIDER / OPENAI_CHAT_MODEL via the
    # agent_effective_provider / agent_effective_model properties.
    AGENT_PROVIDER: str = ""
    AGENT_MODEL: str = ""
    AGENT_ENABLE_DEEPAGENTS: bool = False
    AGENT_MAX_HISTORY_TURNS: int = 10
    AGENT_RECURSION_LIMIT: int = 25
    AGENT_SYSTEM_PROMPT: str = (
        "You are the YOLO System assistant. You help users understand YOLO detection "
        "results, analyse their detection history, and produce concise reports. "
        "You never run YOLO inference yourself; you only read existing detection records. "
        "You never modify or delete data. When a request requires admin privileges and "
        "the current user is not admin, respond politely that the action is not allowed."
    )

    # YOLO
    YOLO_DEFAULT_MODEL: str = "pt/bset.pt"
    YOLO_RESULTS_DIR: str = "static/results"
    DETECTION_SOURCE_DIR: str = "static/detections/originals"
    DETECTION_RESULT_DIR: str = "static/detections/results"
    DETECTION_VIDEO_SOURCE_DIR: str = "static/detections/videos/originals"
    DETECTION_VIDEO_RESULT_DIR: str = "static/detections/videos/results"
    DETECTION_PREVIEW_DIR: str = "static/detections/previews"

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    # Accepts comma-separated string from .env or a list
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return v

    @field_validator("CHAT_PROVIDER", mode="before")
    @classmethod
    def normalize_chat_provider(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("AGENT_PROVIDER", mode="before")
    @classmethod
    def normalize_agent_provider(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    @property
    def agent_effective_provider(self) -> str:
        return (self.AGENT_PROVIDER or self.CHAT_PROVIDER or "mock").strip().lower()

    @property
    def agent_effective_model(self) -> str:
        if self.AGENT_MODEL.strip():
            return self.AGENT_MODEL.strip()
        provider = self.agent_effective_provider
        if provider == "ollama":
            return self.OLLAMA_MODEL or "llama3.2"
        if provider == "deepseek":
            return self.DEEPSEEK_CHAT_MODEL or "deepseek-chat"
        return self.OPENAI_CHAT_MODEL or "mock-chat"


settings = Settings()
