from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
END_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    upload_chunk_size_bytes: int = 5 * 1024 * 1024  # 5 МБ
    # TODO поменять на проде
    cookie_secure: bool = False
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    upload_tmp_dir: Path = BASE_DIR / "tmp" / "uploads"

    model_config = SettingsConfigDict(env_file=END_FILE, extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
