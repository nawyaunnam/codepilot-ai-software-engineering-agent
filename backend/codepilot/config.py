from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    admin_username: str = "admin"
    admin_password: str = ""
    cookie_secure: bool = False
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    workspace_root: str = "/workspace"
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = "/tmp/codepilot-embeddings"
    sandbox_token: str = ""
    database_url: str = "sqlite:///./codepilot.db"
    redis_url: str = "redis://localhost:6379/0"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    sandbox_url: str = "http://localhost:8090"
    jwt_secret: str = "development-secret-change-me"
    max_repository_bytes: int = 50_000_000


settings = Settings()
