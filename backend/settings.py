"""Конфигурация — инфраструктура сборки рядом с точкой сборки `main.py`.

`Settings` — где что лежит: база, выгрузки организаторов, артефакты; читается из переменных
окружения и `.env`. Вне слоёв `app` (docs/adr/0001-layers-and-ports.md): `Settings` читают
только точка сборки и офлайн-команды, домен — никогда.
"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent
# Данные организаторов: XML КТРУ и выгрузки СТЕ — в репо.
DATA_DIR = REPO_DIR / "data" / "yandex_disk"
KTRU_XML_DIR = DATA_DIR / "КТРУ" / "xml"
STE_XLSX_DIR = DATA_DIR / "Примеры выгрузок"
# Локальные артефакты: база, снимок КТРУ, словарь — не в git.
VAR_DIR = REPO_DIR / "var"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{VAR_DIR / 'tender.db'}"
    ktru_xml_dir: Path = KTRU_XML_DIR
    aliases_path: Path = REPO_DIR / "data" / "aliases.csv"

    embeddings_url: str | None = None
    embeddings_api_key: SecretStr | None = None
    embeddings_model: str = "qwen-embedding"
    embeddings_repository: str = "Qwen/Qwen3-Embedding-0.6B"
    embeddings_dimension: int = Field(default=1024, ge=1)
    embeddings_revision: str = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
    embeddings_query_instruction: str = (
        "Given a product description, retrieve the matching product group"
    )
