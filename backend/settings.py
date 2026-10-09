"""Конфигурация — инфраструктура сборки рядом с точкой сборки `main.py`.

`Settings` — где что лежит: база, выгрузки организаторов, словарь синонимов, артефакты, адрес
модели эмбеддингов; читается из переменных окружения и `.env` (пример — `backend/.env.example`).
Вне слоёв `app` (docs/adr/0001-layers-and-ports.md): `Settings` читают только точка сборки и
офлайн-команды, домен — никогда.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent
# Данные организаторов: XML КТРУ и выгрузки СТЕ — в репо.
DATA_DIR = REPO_DIR / "data" / "yandex_disk"
KTRU_XML_DIR = DATA_DIR / "КТРУ" / "xml"
STE_XLSX_DIR = DATA_DIR / "Примеры выгрузок"
# Словарь синонимов групп КТРУ — данные с источником каждой записи, в репо.
ALIASES_CSV = REPO_DIR / "data" / "aliases.csv"
# Локальные артефакты: база, снимок КТРУ, словарь — не в git.
VAR_DIR = REPO_DIR / "var"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{VAR_DIR / 'tender.db'}"
    ktru_xml_dir: Path = KTRU_XML_DIR
    aliases_csv: Path = ALIASES_CSV
    # OpenAI-совместимый сервис эмбеддингов, адрес без пути: `http://host:8089`. Без адреса
    # поиск отвечает 503, остальное работает.
    embeddings_url: str | None = None
    embeddings_api_key: str | None = None
    embeddings_model: str = "Qwen/Qwen3-Embedding-0.6B"
