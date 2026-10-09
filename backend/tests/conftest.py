"""Фикстуры: справочник КТРУ в маленькой XML-выгрузке, база SQLite во временном каталоге со
схемой из миграций и приложение на ней.

Набор не ходит в сеть и не читает выгрузки организаторов: `ktru_dir` пишет XML той же структуры,
что у ЕИС, на две позиции.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.domain.catalog import CATEGORIES
from main import create_app, sync_catalog
from settings import BACKEND_DIR, Settings

HEAD = (
    "<?xml version='1.0' encoding='UTF-8'?>\n"
    '<export xmlns="http://zakupki.gov.ru/oos/export/1" '
    'xmlns:oos="http://zakupki.gov.ru/oos/types/1"><nsiKTRUs>'
)
TAIL = "</nsiKTRUs></export>"

TABLE = """
<oos:position><oos:data>
  <oos:code>31.01.11.150-00000001</oos:code>
  <oos:name>Стол письменный</oos:name>
  <oos:OKPD2><oos:code>31.01.11.150</oos:code><oos:name>Мебель для офисов</oos:name></oos:OKPD2>
  <oos:isTemplate>false</oos:isTemplate>
  <oos:OKEIs><oos:OKEI><oos:code>796</oos:code><oos:name>Штука</oos:name></oos:OKEI></oos:OKEIs>
  <oos:characteristics>
    <oos:characteristic>
      <oos:code>ch-material</oos:code><oos:name>Материал столешницы</oos:name>
      <oos:type>1</oos:type><oos:isRequired>true</oos:isRequired><oos:choiceType>1</oos:choiceType>
      <oos:values>
        <oos:value><oos:valueCode>v-ldsp</oos:valueCode>
          <oos:qualityDescription>ЛДСП</oos:qualityDescription></oos:value>
        <oos:value><oos:valueCode>v-wood</oos:valueCode>
          <oos:qualityDescription>Массив дерева</oos:qualityDescription></oos:value>
      </oos:values>
    </oos:characteristic>
    <oos:characteristic>
      <oos:code>ch-length</oos:code><oos:name>Длина</oos:name>
      <oos:type>2</oos:type><oos:isRequired>false</oos:isRequired><oos:choiceType>1</oos:choiceType>
      <oos:values>
        <oos:value><oos:valueCode>v-len</oos:valueCode>
          <oos:OKEI><oos:code>006</oos:code><oos:name>Метр</oos:name></oos:OKEI>
          <oos:rangeSet><oos:valueRange>
            <oos:min>1</oos:min><oos:minMathNotation>greaterOrEqual</oos:minMathNotation>
            <oos:max>2</oos:max><oos:maxMathNotation>less</oos:maxMathNotation>
          </oos:valueRange></oos:rangeSet></oos:value>
      </oos:values>
    </oos:characteristic>
    <oos:characteristic>
      <oos:code>ch-old</oos:code><oos:name>Устаревшая</oos:name><oos:actual>false</oos:actual>
      <oos:type>1</oos:type>
    </oos:characteristic>
  </oos:characteristics>
</oos:data></oos:position>
"""

AXE = """
<oos:position><oos:data>
  <oos:code>25.73.30.110-00000002</oos:code>
  <oos:name>Топор</oos:name>
  <oos:OKPD2><oos:code>25.73.30.110</oos:code><oos:name>Инструмент ручной</oos:name></oos:OKPD2>
  <oos:isTemplate>false</oos:isTemplate>
</oos:data></oos:position>
"""

TABLE_CODE = "31.01.11.150-00000001"


def write_ktru(directory: Path) -> Path:
    positions = {"Мебель": TABLE, "Инструменты": AXE}
    directory.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        text = HEAD + positions.get(category, "") + TAIL
        (directory / f"{category}.xml").write_text(text, encoding="utf-8")
    return directory


@pytest.fixture
def ktru_dir(tmp_path: Path) -> Path:
    return write_ktru(tmp_path / "ktru")


def migrate(database_url: str) -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


@pytest.fixture
def settings(tmp_path: Path, ktru_dir: Path) -> Settings:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", ktru_xml_dir=ktru_dir)
    migrate(settings.database_url)
    return settings


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def synced(settings: Settings) -> Settings:
    sync_catalog(settings)
    return settings
