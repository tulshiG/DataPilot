# from pydantic_settings import BaseSettings

# class Settings(BaseSettings):
#     DATABASE_URL: str
#     SECRET_KEY: str
#     ALGORITHM: str = "HS256"
#     ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
#     PROJECT_NAME: str = "DataPilot AI"

#     # --- AI Engine Settings ---
#     OLLAMA_HOST: str = "http://localhost:11434"
#     OLLAMA_MODEL: str = "mistral"
#     OLLAMA_TIMEOUT: int = 60
#     EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
#     RAG_TOP_K: int = 8
#     RAG_MIN_SCORE: float = 0.2

#     class Config:
#         env_file = ".env"

# settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str

    # Security Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Application Configuration
    PROJECT_NAME: str = "DataPilot AI"
    FRONTEND_URL: str = "https://data-pilot-kappa.vercel.app"

    # Server Configuration
    PORT: int = 8000

    # AI Engine Settings
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OLLAMA_TIMEOUT: int = 60

    # Embedding and RAG Settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_TOP_K: int = 8
    RAG_MIN_SCORE: float = 0.2

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
