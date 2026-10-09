"""Конфигурация — инфраструктура сборки рядом с точкой сборки `main.py`.

`Settings` — где что лежит: база, выгрузки организаторов, артефакты; читается из переменных
окружения и `.env`. Вне слоёв `app` (docs/adr/0001-layers-and-ports.md): `Settings` читают
только точка сборки и офлайн-команды, домен — никогда.
"""

from pathlib import Path

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
