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
    # Log every SQL statement (with bound parameters). Off by default: the
    # parameters include password hashes and personal data.
    DB_ECHO: bool = False

    # Public signup stays configurable for local development; lab deployment disables it.
    ALLOW_REGISTRATION: bool = True

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    STATIC_URL_EXPIRE_SECONDS: int = 3600  # signed /static URLs for <img> tags

    # Failed-login throttling (0 disables a limit). Counts reset on success
    # for the account; the per-IP limit catches guessing across accounts.
    LOGIN_MAX_FAILURES_PER_ACCOUNT: int = 5
    LOGIN_MAX_FAILURES_PER_IP: int = 20
    LOGIN_FAILURE_WINDOW_SECONDS: int = 900

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

    # LLM access policy (applies to /api/chat and /api/agent).
    # Per-request model overrides must be on these allowlists; the configured
    # default model of each provider is always allowed. Empty = built-in
    # defaults (see app/services/llm_policy.py). Ollama is limited to the
    # models actually installed on the local daemon.
    OPENAI_ALLOWED_MODELS: Annotated[List[str], NoDecode] = []
    DEEPSEEK_ALLOWED_MODELS: Annotated[List[str], NoDecode] = []
    # Per-user request budget across every LLM endpoint (0 disables).
    LLM_RATE_LIMIT_PER_MINUTE: int = 20
    # Per-user daily cap for paid providers (openai / deepseek; 0 disables).
    LLM_PAID_DAILY_LIMIT: int = 200

    # Agent (Phase 6A-1)
    # Empty values fall back to CHAT_PROVIDER / OPENAI_CHAT_MODEL via the
    # agent_effective_provider / agent_effective_model properties.
    AGENT_PROVIDER: str = ""
    AGENT_MODEL: str = ""
    AGENT_ENABLE_DEEPAGENTS: bool = False
    # "tool_calling" (default since the 2026-10-19 eval, tests/evals/
    # evaluate_agent_engines.py): LangChain create_agent picks read-only tools
    # itself (tool_agent.py); falls back to the pipeline for mock / report /
    # vision. "pipeline": keyword/mode routing + one LLM call (graph.py).
    AGENT_ENGINE: str = "tool_calling"
    AGENT_MAX_TOOL_CALLS: int = 8
    # Ollama model the agent uses when AGENT_MODEL is empty (chat keeps
    # OLLAMA_MODEL). gemma4 scored best in the engine eval.
    AGENT_OLLAMA_MODEL: str = "gemma4"
    AGENT_MAX_HISTORY_TURNS: int = 10
    AGENT_RECURSION_LIMIT: int = 25
    # When true, explain_detection / report modes attach the annotated result
    # image (base64) to the LLM call so vision-capable models (e.g. OpenAI
    # gpt-4o/gpt-4.1, Ollama llava/qwen2-vl) can describe what they actually
    # see, in addition to the structured bbox/class data. Only enable this
    # with a provider+model that supports image inputs — non-vision models
    # will fail the call and the agent falls back to its "model unavailable"
    # message (no crash, but no answer either).
    AGENT_ENABLE_VISION: bool = False
    AGENT_VISION_MAX_IMAGE_BYTES: int = 6 * 1024 * 1024
    AGENT_SYSTEM_PROMPT: str = (
        "You are the YOLO System assistant. You help users understand YOLO detection "
        "results, analyse their detection history, and produce concise reports. "
        "You never run YOLO inference yourself; you only read existing detection records. "
        "You never modify or delete data. When a request requires admin privileges and "
        "the current user is not admin, respond politely that the action is not allowed."
    )

    # YOLO
    YOLO_DEFAULT_MODEL_KEY: str = "seven_class_asff"
    YOLO_DEFAULT_MODEL: str = "pt/bset.pt"
    YOLO_RESULTS_DIR: str = "static/results"
    DETECTION_SOURCE_DIR: str = "static/detections/originals"
    DETECTION_RESULT_DIR: str = "static/detections/results"
    DETECTION_VIDEO_SOURCE_DIR: str = "static/detections/videos/originals"
    DETECTION_VIDEO_RESULT_DIR: str = "static/detections/videos/results"
    DETECTION_PREVIEW_DIR: str = "static/detections/previews"
    # Phase 1 batch image analysis. Kept at 100 for the initial rollout;
    # raise once background processing throughput has been validated in
    # production (README/AGENTS.md tracks this as a follow-up).
    DETECTION_BATCH_MAX_FILES: int = 100
    # Per-class threshold detection disables Ultralytics' own NMS (iou=1.0) so
    # the raw candidate boxes can be re-suppressed with each class's own IoU.
    # Ultralytics applies `max_det` *after* NMS, so with suppression disabled
    # the default (300) would truncate dense images before we ever run our own
    # NMS. This ceiling only applies to per-class requests.
    DETECTION_PERCLASS_MAX_DET: int = 3000

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    # Accepts comma-separated string from .env or a list
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", "OPENAI_ALLOWED_MODELS", "DEEPSEEK_ALLOWED_MODELS", mode="before")
    @classmethod
    def parse_comma_separated_list(cls, v: Any) -> List[str]:
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

    @field_validator("AGENT_ENGINE", mode="before")
    @classmethod
    def normalize_agent_engine(cls, v: Any) -> str:
        if isinstance(v, str):
            value = v.strip().lower() or "tool_calling"
            if value not in ("pipeline", "tool_calling"):
                raise ValueError("AGENT_ENGINE must be 'pipeline' or 'tool_calling'")
            return value
        return v

    @field_validator("AGENT_PROVIDER", mode="before")
    @classmethod
    def normalize_agent_provider(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in ("production", "prod")

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
            return self.AGENT_OLLAMA_MODEL or self.OLLAMA_MODEL or "gemma4"
        if provider == "deepseek":
            return self.DEEPSEEK_CHAT_MODEL or "deepseek-chat"
        return self.OPENAI_CHAT_MODEL or "mock-chat"


settings = Settings()
