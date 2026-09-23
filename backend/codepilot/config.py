from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
    database_url:str="sqlite:///./codepilot.db"
    redis_url:str="redis://localhost:6379/0"
    llm_api_key:str=""
    llm_model:str="gpt-4.1-mini"
    sandbox_url:str="http://localhost:8090"
    jwt_secret:str="development-secret-change-me"
    max_repository_bytes:int=50_000_000
settings=Settings()

