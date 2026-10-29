"""Start the website and API together; publish only the website via cpolar."""

from __future__ import annotations

import argparse
from html import unescape
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
PID_FILE = RUNTIME / "app.pid"
CPOLAR_PID = RUNTIME / "cpolar.pid"


def private_runtime() -> None:
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    RUNTIME.chmod(0o700)
    (RUNTIME / "logs").mkdir(mode=0o700, exist_ok=True)


def log_file(name: str):
    path = RUNTIME / "logs" / name
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    return os.fdopen(descriptor, "ab", buffering=0)


def running(path: Path, marker: str) -> int | None:
    try:
        pid = int(path.read_text().strip())
        os.kill(pid, 0)
        cmdline = Path(f"/proc/{pid}/cmdline")
        if cmdline.exists() and marker not in cmdline.read_text():
            return None
        return pid
    except (OSError, ValueError):
        return None


def healthy(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def env_value(name: str) -> str:
    if value := os.environ.get(name):
        return value
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            key, separator, value = line.strip().partition("=")
            if separator and key == name:
                parts = shlex.split(value, comments=True)
                return parts[0] if parts else ""
    return ""


def cpolar_urls(body: str) -> list[str]:
    """Read the CLI inspector's JSON.parse payload without executing JavaScript."""
    try:
        data = json.loads(body)
    except ValueError:
        match = re.search(r'window\.data\s*=\s*JSON\.parse\(\s*("(?:[^"\\]|\\.)*")\s*\)', unescape(body))
        if not match:
            return []
        try:
            data = json.loads(json.loads(match.group(1)))
        except (ValueError, TypeError):
            return []
    if not isinstance(data, dict):
        return []
    state = data.get("UiState", {})
    tunnels = state.get("Tunnels", []) if isinstance(state, dict) else []
    if not tunnels:
        tunnels = data.get("tunnels", [])
    if not isinstance(tunnels, list):
        return []
    urls = [item.get("PublicUrl", item.get("public_url", "")) for item in tunnels if isinstance(item, dict)]
    return list(dict.fromkeys(url for url in urls if isinstance(url, str) and url.startswith("https://")))


def supervise() -> int:
    import fcntl

    private_runtime()
    lock = (RUNTIME / "app.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 1
    PID_FILE.write_text(str(os.getpid()))
    children: list[subprocess.Popen] = []

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        commands = [
            ([str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000"], ROOT, "api.log"),
            ([shutil.which("node") or "node", str(ROOT / "frontend/node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", "3000"], ROOT / "frontend", "web.log"),
        ]
        for command, cwd, filename in commands:
            with log_file(filename) as log:
                children.append(subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT))
        while all(child.poll() is None for child in children):
            time.sleep(1)
        print("子进程已退出，请查看 .runtime/logs/", flush=True)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        PID_FILE.unlink(missing_ok=True)


def start() -> None:
    private_runtime()
    if not running(PID_FILE, "manage.py"):
        if healthy("http://127.0.0.1:3000") or healthy("http://127.0.0.1:8000/api/v1/health"):
            raise SystemExit("3000 或 8000 端口已被其他服务使用，请先停止该服务。")
        with log_file("manager.log") as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_serve"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(90):
            if healthy("http://127.0.0.1:3000/api/v1/health") and healthy("http://127.0.0.1:3000"):
                break
            if process.poll() is not None:
                raise SystemExit("启动失败，请查看 .runtime/logs/api.log 和 web.log。")
            time.sleep(0.5)
        else:
            process.terminate()
            process.wait(timeout=25)
            raise SystemExit("服务启动超时，已停止。请查看 .runtime/logs/。")
    print("CareerPilot 已启动：http://127.0.0.1:3000")
    print("日志：.runtime/logs/；停止：make stop")


def public() -> None:
    binary = shutil.which("cpolar") or str(RUNTIME / "bin/cpolar")
    if not Path(binary).is_file():
        raise SystemExit("cpolar 尚未安装。请运行 ./scripts/install-cpolar.sh 后重试 ./start.sh --public。")
    token = env_value("CPOLAR_AUTHTOKEN")
    config = RUNTIME / "cpolar.yml"
    if token:
        descriptor = os.open(config, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as file:
            file.write("authtoken: " + json.dumps(token) + "\nweb_addr: 127.0.0.1:4040\n")
    elif not config.exists() and not (Path.home() / ".cpolar/cpolar.yml").exists():
        raise SystemExit("网站已运行。发布还需 cpolar 免费账号的 authtoken：写入私有 .env 的 CPOLAR_AUTHTOKEN，再运行 ./start.sh --public。")
    process = None
    if not running(CPOLAR_PID, "cpolar"):
        command = [binary, "http", "-inspect-addr", "127.0.0.1:4040"]
        if config.exists():
            command += ["-config", str(config)]
        command += ["3000"]
        with log_file("cpolar.log") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        CPOLAR_PID.write_text(str(process.pid))
    for _ in range(30 if process else 1):
        if process is not None and process.poll() is not None:
            CPOLAR_PID.unlink(missing_ok=True)
            raise SystemExit("cpolar 启动失败，请查看 .runtime/logs/cpolar.log（不要公开日志中的账号信息）。")
        # cpolar 3.3.12 embeds UiState.Tunnels[].PublicUrl in the inspector HTML.
        # Keep the JSON endpoint as a fallback for other compatible versions.
        for endpoint in ("/", "/api/tunnels"):
            try:
                with urlopen("http://127.0.0.1:4040" + endpoint, timeout=2) as response:
                    urls = cpolar_urls(response.read(2 * 1024 * 1024).decode("utf-8"))
                if urls:
                    print("免费公网 HTTPS 地址：" + urls[0])
                    return
            except (OSError, ValueError):
                pass
        if process is not None:
            time.sleep(1)
    print("cpolar 已运行；在 http://127.0.0.1:4040 或 cpolar 控制台查看在线隧道。")


def stop() -> None:
    for path, marker in [(CPOLAR_PID, "cpolar"), (PID_FILE, "manage.py")]:
        pid = running(path, marker)
        if pid:
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                if not running(path, marker):
                    break
                time.sleep(0.2)
        path.unlink(missing_ok=True)
    print("CareerPilot 与项目 cpolar 隧道已停止。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "stop", "status", "_serve"])
    parser.add_argument("--public", action="store_true", help="使用 cpolar 免费随机域名发布")
    args = parser.parse_args()
    if args.command == "_serve":
        return supervise()
    if args.command == "stop":
        stop()
    elif args.command == "status":
        print("运行中：http://127.0.0.1:3000" if running(PID_FILE, "manage.py") and healthy("http://127.0.0.1:3000/api/v1/health") else "未运行")
    else:
        start()
        if args.public:
            public()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
