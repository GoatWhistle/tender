"""Домен: понятия и правила КТРУ и анализа без библиотек хранения, схем и HTTP.

Зависимости слоёв направлены сюда (docs/adr/0001-layers-and-ports.md): `domain` не импортирует
SQLAlchemy, Pydantic, FastAPI и lxml — это проверяет `tests/test_layers.py`.
"""
