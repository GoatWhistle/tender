"""Install the same commands on a Vast container without Docker-in-Docker."""

import argparse
import shlex
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--profile", choices=("4b", "9b"), default="4b")
    args = parser.parse_args()
    root = args.root.resolve()
    model_dir = root / ("models-9b" if args.profile == "9b" else "models")
    manifest_dir = root / "profiles/9b" if args.profile == "9b" else root
    memory_budget = "0.60" if args.profile == "9b" else "0.35"
    for name, mode, port in (
        ("qwen-embedding", "embedding", 8081),
        ("qwen-engine", "extractor", 8083),
        ("qwen-extractor", "strict", 8082),
    ):
        script = Path("/opt/supervisor-scripts") / f"{name}.sh"
        script.write_text(
            "#!/bin/bash\nset -eo pipefail\n"
            "utils=/opt/supervisor-scripts/utils\n"
            '. "${utils}/logging.sh"\n. "${utils}/environment.sh"\n'
            f"export PATH={shlex.quote(str(root / '.venv/bin'))}:$PATH\n"
            f"export QWEN_MODEL_DIR={shlex.quote(str(model_dir))}\n"
            f"export QWEN_MANIFEST_DIR={shlex.quote(str(manifest_dir))}\n"
            f"export EXTRACTOR_GPU_MEMORY_UTILIZATION={memory_budget}\n"
            f"export QWEN_HOST=127.0.0.1 QWEN_PORT={port}\n"
            "export QWEN_ENGINE_URL=http://127.0.0.1:8083\n"
            f"until test -f {shlex.quote(str(model_dir / 'artifacts.json'))}; do sleep 2; done\n"
            + (
                "until curl -fsS http://127.0.0.1:8081/health >/dev/null 2>&1; do sleep 2; done\n"
                if mode == "extractor"
                else ""
            )
            + f"exec bash {shlex.quote(str(root / 'launch.sh'))} {mode}\n"
        )
        script.chmod(0o755)
        config = Path("/etc/supervisor/conf.d") / f"{name}.conf"
        config.write_text(
            f'[program:{name}]\nenvironment=PROC_NAME="%(program_name)s"\n'
            f"command={script}\nautostart=true\nautorestart=unexpected\n"
            "startsecs=10\nstartretries=3\nstopwaitsecs=120\nstopsignal=TERM\n"
            "stopasgroup=true\nkillasgroup=true\n"
            "stdout_logfile=/dev/stdout\nredirect_stderr=true\nstdout_logfile_maxbytes=0\n"
        )
    subprocess.run(["supervisorctl", "reread"], check=True)
    subprocess.run(["supervisorctl", "update"], check=True)


if __name__ == "__main__":
    main()
