"""Фикстуры: справочник КТРУ в маленькой XML-выгрузке, база SQLite во временном каталоге со
схемой из миграций и приложение на ней.

Набор не ходит в сеть и не читает выгрузки организаторов: `ktru_dir` пишет XML той же структуры,
что у ЕИС. Дерево групп: стол — позиция без родителя и без потомков, шкаф — шаблон с двумя
потомками, халат — шаблон без потомков, топор — позиция без родителя, у молотка родитель
отсутствует в справочнике.
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
      <oos:type>1</oos:type><oos:kind>2</oos:kind><oos:isRequired>true</oos:isRequired>
      <oos:choiceType>2</oos:choiceType>
      <oos:values>
        <oos:value><oos:valueCode>v-ldsp</oos:valueCode>
          <oos:qualityDescription>ЛДСП</oos:qualityDescription></oos:value>
        <oos:value><oos:valueCode>v-wood</oos:valueCode>
          <oos:qualityDescription>Массив дерева</oos:qualityDescription></oos:value>
      </oos:values>
    </oos:characteristic>
    <oos:characteristic>
      <oos:code>ch-length</oos:code><oos:name>Длина</oos:name>
      <oos:type>2</oos:type><oos:kind>1</oos:kind><oos:isRequired>false</oos:isRequired>
      <oos:choiceType>1</oos:choiceType>
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
CABINET_CODE = "31.01.12.110-00000001"
CABINET_CHILDREN = ["31.01.12.110-00000002", "31.01.12.110-00000003"]
ROBE_CODE = "14.12.30.160-00000001"
AXE_CODE = "25.73.30.110-00000002"
HAMMER_CODE = "25.73.30.120-00000005"


def position(code: str, name: str, *, template: bool = False, parent: str | None = None) -> str:
    parent_info = f"<oos:parentPositionInfo><oos:code>{parent}</oos:code></oos:parentPositionInfo>"
    return f"""
<oos:position><oos:data>
  <oos:code>{code}</oos:code>
  <oos:name>{name}</oos:name>
  <oos:OKPD2><oos:code>{code.split("-")[0]}</oos:code><oos:name>{name}</oos:name></oos:OKPD2>
  <oos:isTemplate>{str(template).lower()}</oos:isTemplate>
  {parent_info if parent else ""}
</oos:data></oos:position>
"""


CABINET = position(CABINET_CODE, "Шкаф для одежды", template=True).replace(
    "</oos:data>",
    """<oos:characteristics><oos:characteristic>
    <oos:code>ch-cab</oos:code><oos:name>Материал</oos:name>
    <oos:type>1</oos:type><oos:kind>3</oos:kind><oos:choiceType>2</oos:choiceType>
  </oos:characteristic></oos:characteristics></oos:data>""",
)
# Старая выгрузка без `kind`: вид характеристики берётся из `choiceType`.
ROBE = position(ROBE_CODE, "Халат производственный", template=True).replace(
    "</oos:data>",
    """<oos:characteristics><oos:characteristic>
    <oos:code>ch-size</oos:code><oos:name>Размер</oos:name>
    <oos:type>1</oos:type><oos:choiceType>2</oos:choiceType>
  </oos:characteristic></oos:characteristics></oos:data>""",
)
FURNITURE = (
    TABLE
    + CABINET
    + position(CABINET_CHILDREN[0], "Шкаф для одежды металлический", parent=CABINET_CODE)
    + position(CABINET_CHILDREN[1], "Шкаф для одежды деревянный", parent=CABINET_CODE)
)
TOOLS = AXE + position(HAMMER_CODE, "Молоток", parent="25.73.30.120-00000000")


def write_ktru(directory: Path) -> Path:
    positions = {"Мебель": FURNITURE, "Одежда": ROBE, "Инструменты": TOOLS}
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
