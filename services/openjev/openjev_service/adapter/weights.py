"""Атомарная загрузка закреплённых файлов с проверкой до импорта кода."""

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path

from ..config import REVISION

MANIFEST = json.loads(Path(__file__).with_name("model_manifest.json").read_text())


def matches(path: Path, expected: dict) -> bool:
    if not path.is_file() or path.stat().st_size != expected["size"]:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == expected["sha256"]


def ensure_weights(root: Path, *, offline=False, manifest=None, download=None) -> Path:
    """Том сохраняется при перезапуске; корректные файлы повторно не скачиваются.

    Каждый запуск проверяет все хеши, включая 9 GB весов. Изменяемая ссылка или
    отметка о прошлой проверке не заменяет проверку реальных байтов.
    """
    manifest = MANIFEST if manifest is None else manifest
    download = urllib.request.urlretrieve if download is None else download
    root.mkdir(parents=True, exist_ok=True)
    # POSIX-блокировка защищает также от параллельного запуска загрузчика.
    import fcntl

    with (root / ".download.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for filename, expected in manifest.items():
            target = root / filename
            if matches(target, expected):
                continue
            if offline:
                raise RuntimeError(
                    f"Закреплённый файл модели отсутствует или повреждён: {filename}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".partial")
            try:
                url = f"https://huggingface.co/AlexWortega/openjev/resolve/{REVISION}/{filename}"
                download(url, temporary)
                if not matches(temporary, expected):
                    raise RuntimeError(f"Контрольная сумма не совпадает: {filename}")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
    return root


def main():
    from ..config import Settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default=Settings.from_env().model_dir)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    ensure_weights(Path(args.model_dir), offline=args.offline)


if __name__ == "__main__":
    main()
