#!/usr/bin/env bash
# Install the official client locally; this does not create an account or tunnel.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
command -v python3 >/dev/null || { echo "需要 Python 3，请先安装后重试。" >&2; exit 1; }

python3 - "$ROOT" <<'PY'
import io
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from urllib.error import URLError
from urllib.request import urlopen
import zipfile

version = "3.3.12"
architectures = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
architecture = architectures.get(platform.machine().lower())
if platform.system() != "Linux" or architecture is None:
    raise SystemExit("此脚本支持 Linux x86_64 / arm64；其他系统请访问 https://www.cpolar.com/download。")

destination = Path(sys.argv[1]) / ".runtime" / "bin" / "cpolar"
destination.parent.mkdir(parents=True, exist_ok=True)
url = f"https://www.cpolar.com/static/downloads/releases/{version}/cpolar-stable-linux-{architecture}.zip"
temporary = None
try:
    print(f"下载官方 cpolar {version}（{architecture}）…", flush=True)
    with urlopen(url, timeout=90) as response:
        if not response.url.startswith("https://"):
            raise ValueError("下载地址必须保持 HTTPS")
        archive = response.read(80 * 1024 * 1024 + 1)
    if len(archive) > 80 * 1024 * 1024:
        raise ValueError("下载文件超过大小限制")
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        candidates = [item for item in package.infolist() if not item.is_dir() and item.filename.rsplit("/", 1)[-1] == "cpolar"]
        if len(candidates) != 1 or candidates[0].file_size > 80 * 1024 * 1024:
            raise ValueError("ZIP 中没有唯一的 cpolar 可执行文件")
        binary = package.read(candidates[0])  # Reading also validates the ZIP entry's CRC.
    if not binary.startswith(b"\x7fELF"):
        raise ValueError("下载文件不是 Linux ELF 可执行文件")
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".cpolar-", delete=False) as file:
        temporary = Path(file.name)
        file.write(binary)
    temporary.chmod(0o755)
    check = subprocess.run([str(temporary), "version"], check=True, capture_output=True, text=True, timeout=10)
    if f"cpolar version {version}" not in check.stdout:
        raise ValueError("客户端版本验证失败")
    os.replace(temporary, destination)
    print(check.stdout.strip())
    print(f"已安装：{destination}\n下一步：在私有 .env 配置 CPOLAR_AUTHTOKEN，再运行 ./start.sh --public。")
except (OSError, URLError, ValueError, zipfile.BadZipFile, RuntimeError, subprocess.SubprocessError) as error:
    raise SystemExit(f"cpolar 安装失败：{error}") from None
finally:
    if temporary is not None:
        temporary.unlink(missing_ok=True)
PY
