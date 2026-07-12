"""
Central configuration, loaded from environment variables (.env).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/interview_coach"

    # Auth
    jwt_secret: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # Gemini (Google AI Studio) — free tier, no credit card required
    # Get a key at https://aistudio.google.com/apikey
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"  # generous free tier as of mid-2026; check aistudio.google.com for current free-tier models

    # Fallback LLM providers — tried in order (Gemini -> Groq -> OpenRouter)
    # whenever the previous one raises (quota exhausted, rate limited, down,
    # etc). Leave an API key blank to skip that provider entirely rather
    # than attempting and failing. Get keys at https://console.groq.com/keys
    # and https://openrouter.ai/keys
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct"

    # File upload
    max_upload_mb: int = 10
    upload_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
