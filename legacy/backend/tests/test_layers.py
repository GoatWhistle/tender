"""Направление зависимостей слоёв (docs/adr/0001-layers-and-ports.md).

В `app` только пакеты слоёв. `domain` не знает библиотек хранения, схем, HTTP, разбора файлов и
конфига и не тянет их через другие пакеты `app`; `usecase` не знает реализаций портов и
контроллеров; ORM — только в `repository`, FastAPI — только в `controller`; адаптеры и
контроллеры не знают хранилищ, а хранилища — адаптеров и HTTP; in-memory хранилища не знают
SQLAlchemy и ничего из `app`, кроме домена, портов и себя, заглушки моделей — тоже; библиотек
моделей в `app` нет. Импорты читаются из исходников, а не из `sys.modules`: так ловится и импорт
внутри функции, и импорт под `TYPE_CHECKING`; относительный импорт сводится к полному имени.
"""

import ast
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from settings import BACKEND_DIR, REPO_DIR


@dataclass(frozen=True)
class Rule:
    banned: tuple[str, ...]
    allowed: tuple[str, ...] = ()


LAYERS = ("domain", "usecase", "controller", "adapter", "repository")

DOMAIN = Rule(
    banned=(
        "sqlalchemy",
        "pydantic",
        "pydantic_settings",
        "fastapi",
        "lxml",
        "openpyxl",
        "settings",
        "httpx",
        "app",
    ),
    allowed=("app.domain",),
)
# Сценарии не знают реализаций портов: ни адаптеров, ни репозиториев.
# Порты моделей тоже: на входе и выходе домен, а не клиенты HTTP.
USECASE = Rule(
    banned=("sqlalchemy", "fastapi", "httpx", "app.adapter", "app.repository", "app.controller")
)
ADAPTER = Rule(banned=("sqlalchemy", "fastapi", "app.repository", "app.controller"))
# Контроллер получает от сценария доменные значения, а не строки ORM.
CONTROLLER = Rule(banned=("sqlalchemy", "app.repository", "app.adapter"))
REPOSITORY = Rule(banned=("fastapi", "pydantic", "app.adapter", "app.controller"))
MEMORY = Rule(
    banned=("sqlalchemy", "app"),
    allowed=("app.domain", "app.usecase", "app.repository.memory"),
)
STUB = Rule(
    banned=("sqlalchemy", "fastapi", "app"),
    allowed=("app.domain", "app.usecase.interface", "app.adapter.stub"),
)


def _within(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == p or module.startswith(f"{p}.") for p in prefixes)


def imported_modules(source: str, package: str) -> set[str]:
    """Модули, которые импортирует исходник из пакета `package`, — полными именами."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - node.level + 1]
                base = ".".join([*parts, node.module] if node.module else parts)
            else:
                base = node.module or ""
            modules.add(base)
            modules.update(f"{base}.{alias.name}" for alias in node.names)
    return modules


def violations(package: Path, rule: Rule) -> list[str]:
    """Запрещённые импорты в пакете — строками «файл: модуль». Имена модулей считаются от
    каталога, в котором лежит корневой пакет `app`."""
    root = next(p for p in package.parents if p.name == "app").parent
    found = []
    for path in sorted(package.rglob("*.py")):
        # Пакет файла: для `__init__.py` — сам каталог, для модуля — каталог, где он лежит.
        own = ".".join(path.relative_to(root).parent.parts)
        for module in sorted(imported_modules(path.read_text(encoding="utf-8"), own)):
            if _within(module, rule.banned) and not _within(module, rule.allowed):
                found.append(f"{path.relative_to(root)}: {module}")
    return found


@pytest.mark.parametrize(
    ("layer", "rule"),
    [
        ("domain", DOMAIN),
        ("usecase", USECASE),
        ("adapter", ADAPTER),
        ("controller", CONTROLLER),
        ("repository", REPOSITORY),
        ("repository/memory", MEMORY),
        ("adapter/stub", STUB),
    ],
)
def test_layer_imports_only_inward(layer: str, rule: Rule) -> None:
    package = BACKEND_DIR / "app" / layer
    assert (package / "__init__.py").is_file(), f"нет пакета app/{layer}"
    assert violations(package, rule) == []


def plant(tmp_path: Path, layer: str, source: str) -> Path:
    package = tmp_path / "app" / layer
    package.mkdir(parents=True)
    for directory in [package, *package.relative_to(tmp_path / "app").parents]:
        (tmp_path / "app" / directory / "__init__.py").write_text("")
    (package / "bad.py").write_text(source)
    return package


@pytest.mark.parametrize(
    ("layer", "rule", "source", "caught"),
    [
        ("domain", DOMAIN, "from sqlalchemy.orm import Mapped\n", "sqlalchemy.orm"),
        ("domain", DOMAIN, "def f() -> None:\n    import fastapi\n", "fastapi"),
        ("domain", DOMAIN, "from lxml import etree\n", "lxml"),
        ("domain", DOMAIN, "from app.repository.database import Base\n", "app.repository.database"),
        ("domain", DOMAIN, "from settings import Settings\n", "settings"),
        ("domain", DOMAIN, "from app.usecase.interface import X\n", "app.usecase.interface"),
        ("domain", DOMAIN, "from ..adapter import ktru_xml\n", "app.adapter.ktru_xml"),
        ("usecase", USECASE, "from app.repository import catalog\n", "app.repository"),
        ("usecase", USECASE, "from ..repository.orm import X\n", "app.repository.orm"),
        ("usecase", USECASE, "from app.adapter.ktru_xml import X\n", "app.adapter.ktru_xml"),
        ("usecase", USECASE, "import app.controller.errors\n", "app.controller.errors"),
        ("repository/memory", MEMORY, "from sqlalchemy.orm import Session\n", "sqlalchemy.orm"),
        (
            "repository/memory",
            MEMORY,
            "from ..unit_of_work import SqlUnitOfWork\n",
            "app.repository.unit_of_work",
        ),
        ("adapter", ADAPTER, "from app.repository.orm import X\n", "app.repository.orm"),
        ("adapter/stub", STUB, "from ..ktru_xml import XmlKtruSource\n", "app.adapter.ktru_xml"),
        (
            "adapter/stub",
            STUB,
            "from app.usecase.model_checks import X\n",
            "app.usecase.model_checks",
        ),
        ("controller", CONTROLLER, "from ..repository.orm import X\n", "app.repository.orm"),
        ("controller", CONTROLLER, "from sqlalchemy import select\n", "sqlalchemy"),
        ("repository", REPOSITORY, "from fastapi import Depends\n", "fastapi"),
        ("repository", REPOSITORY, "from ..controller.deps import x\n", "app.controller.deps"),
    ],
)
def test_planted_violation_is_caught(
    tmp_path: Path, layer: str, rule: Rule, source: str, caught: str
) -> None:
    package = plant(tmp_path, layer, source)

    assert any(v.endswith(f": {caught}") for v in violations(package, rule))


def outside_layers(app_dir: Path) -> list[str]:
    """Что лежит в `app` вне пакетов слоёв, кроме `__init__.py` и кэша байткода."""
    allowed = {*LAYERS, "__init__.py", "__pycache__"}
    return sorted(p.name for p in app_dir.iterdir() if p.name not in allowed)


def test_app_holds_only_layers() -> None:
    assert outside_layers(BACKEND_DIR / "app") == []


def test_module_outside_layers_is_caught(tmp_path: Path) -> None:
    for name in LAYERS:
        (tmp_path / name).mkdir()
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "search.py").write_text("")

    assert outside_layers(tmp_path) == ["catalog", "search.py"]


PARSERS = Rule(banned=("lxml", "openpyxl"))


def test_file_parsers_live_only_in_adapters() -> None:
    """Разбор XML ЕИС и выгрузок СТЕ — за портами: lxml и openpyxl в `app` импортирует только
    `app.adapter`."""
    app_dir = BACKEND_DIR / "app"
    packages = [p for p in app_dir.iterdir() if (p / "__init__.py").is_file()]
    found = [v for p in sorted(packages) if p.name != "adapter" for v in violations(p, PARSERS)]
    assert found == []


# Библиотеки моделей: дистрибутив → модуль импорта. Модели — в отдельных сервисах за портами.
MODEL_LIBRARIES = {
    "torch": "torch",
    "transformers": "transformers",
    "sentence-transformers": "sentence_transformers",
    "flagembedding": "FlagEmbedding",
    "accelerate": "accelerate",
    "onnxruntime": "onnxruntime",
    "vllm": "vllm",
    "openai": "openai",
}
MODELS = Rule(banned=tuple(MODEL_LIBRARIES.values()))


def test_model_libraries_stay_out_of_app() -> None:
    app_dir = BACKEND_DIR / "app"
    packages = [p for p in app_dir.iterdir() if (p / "__init__.py").is_file()]
    assert [v for p in sorted(packages) for v in violations(p, MODELS)] == []


def distribution(requirement: str) -> str:
    """Имя дистрибутива из строки зависимости PEP 508, нормализованное по PEP 503."""
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    assert match, requirement
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def test_backend_dependencies_have_no_model_libraries() -> None:
    project = tomllib.loads((BACKEND_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    names = {distribution(r) for r in project["project"]["dependencies"]}
    assert names.isdisjoint(MODEL_LIBRARIES)


@pytest.mark.parametrize(
    ("requirement", "name"),
    [
        ("torch~=2.3", "torch"),
        ("numpy!=1.0", "numpy"),
        ("vllm @ https://example.org/vllm.whl", "vllm"),
        ("Sentence_Transformers[onnx]>=3; python_version>'3.11'", "sentence-transformers"),
    ],
)
def test_distribution_name_is_parsed(requirement: str, name: str) -> None:
    assert distribution(requirement) == name


EVALS = Rule(banned=("evals",))


def test_product_does_not_import_evals() -> None:
    """Зависимости идут от замеров к продукту, обратно — никогда: `main`, `composition`,
    `settings` и `app` не импортируют пакет `evals`."""
    paths = [*(BACKEND_DIR / "app").rglob("*.py")]
    paths += [BACKEND_DIR / f"{name}.py" for name in ("main", "composition", "settings")]
    found = [
        f"{path.relative_to(REPO_DIR)}: {module}"
        for path in sorted(paths)
        for module in sorted(imported_modules(path.read_text(encoding="utf-8"), "app"))
        if _within(module, EVALS.banned)
    ]
    assert found == []


INDEX_LIBRARIES = Rule(banned=("numpy", "sklearn"))


def test_index_libraries_live_only_in_adapters() -> None:
    app_dir = BACKEND_DIR / "app"
    packages = [p for p in app_dir.iterdir() if (p / "__init__.py").is_file()]
    assert [
        v for p in packages if p.name != "adapter" for v in violations(p, INDEX_LIBRARIES)
    ] == []
