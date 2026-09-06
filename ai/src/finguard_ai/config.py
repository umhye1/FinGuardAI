from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", env_file=None, extra="ignore")
    service_token: SecretStr = Field(min_length=32)
    database_url: SecretStr | None = None
    database_host: str | None = None
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "finguard"
    database_user: str = "finguard"
    database_password: SecretStr | None = None
    classifier_mode: Literal["local", "gemini"] = "local"
    classifier_path: Path = Path(".artifacts/classifier.json")
    allow_demo_model: bool = False
    gemini_api_key: SecretStr | None = None
    generation_model: str = Field(default="", max_length=70, pattern=r"^[a-zA-Z0-9._-]*$")
    embedding_model: str = Field(
        default="gemini-embedding-001", min_length=1, max_length=70, pattern=r"^[a-zA-Z0-9._-]+$"
    )
    embedding_dimensions: Literal[768] = 768
    request_timeout_seconds: float = Field(default=4.0, gt=0, le=60)
    retrieval_top_k: int = Field(default=5, ge=1, le=10)
    retrieval_min_score: float = Field(default=0.6, ge=-1, le=1)
    pool_max_size: int = Field(default=4, ge=1, le=16)
    max_concurrent_requests: int = Field(default=4, ge=1, le=16)

    @property
    def connection_info(self) -> str | None:
        if self.database_url:
            return self.database_url.get_secret_value()
        if self.database_host:
            from psycopg.conninfo import make_conninfo

            return make_conninfo(
                host=self.database_host,
                port=self.database_port,
                dbname=self.database_name,
                user=self.database_user,
                password=self.database_password.get_secret_value() if self.database_password else "",
            )
        return None

    @model_validator(mode="after")
    def validate_generation(self):
        if self.classifier_mode == "gemini" and not self.generation_model:
            raise ValueError("AI_GENERATION_MODEL is required for Gemini classification")
        return self
