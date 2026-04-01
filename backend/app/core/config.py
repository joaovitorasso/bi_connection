from pydantic_settings import BaseSettings
import secrets


class Settings(BaseSettings):
    APP_NAME: str = "Power BI Metadata Editor"
    SECRET_KEY: str = secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: list = ["*"]
    AUDIT_LOG_PATH: str = "./audit.log"
    READ_ONLY_MODE: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
