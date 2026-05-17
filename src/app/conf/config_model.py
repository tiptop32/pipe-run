from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GITLAB_BASE_URL: str = "https://gitlab.com"

    REPORTS_DIR: str = "./allure_reports"

    DATABASE_URL: str = "sqlite+aiosqlite:///./data.db"

    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOGLEVEL: str = "INFO"

    model_config = {"extra": "ignore"}
