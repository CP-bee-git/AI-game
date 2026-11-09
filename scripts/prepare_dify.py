import argparse
import base64
import concurrent.futures
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.19.0"


def github(path: str) -> dict:
    if shutil.which("gh"):
        response = subprocess.run(["gh", "api", "repos/langgenius/dify/" + path], capture_output=True, text=True, timeout=30, check=True)
        return json.loads(response.stdout)
    request = urllib.request.Request("https://api.github.com/repos/langgenius/dify/" + path, headers={"User-Agent": "CareerPilot-local-setup"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def prepare():
    destination = ROOT / ".runtime/dify"
    destination.mkdir(parents=True, exist_ok=True)
    tree = github(f"git/trees/{VERSION}?recursive=1")
    docker_files = [item for item in tree["tree"] if item["type"] == "blob" and item["path"].startswith("docker/")]

    def download(item):
        target = destination / item["path"]
        if target.is_file():
            existing = target.read_bytes()
            if hashlib.sha1(b"blob " + str(len(existing)).encode() + b"\0" + existing).hexdigest() == item["sha"]:
                return
        data = github("git/blobs/" + item["sha"])
        content = base64.b64decode(data["content"])
        if hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest() != item["sha"]:
            raise ValueError("Source verification failed: " + item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(download, docker_files))
    private = ROOT / ".private/dify"
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    private.chmod(0o700)
    token_file = private / "tools.env"
    if not token_file.exists():
        token_file.write_text("AGENT_TOOLS_TOKEN=" + secrets.token_urlsafe(48) + "\n")
        token_file.chmod(0o600)
    env = destination / "docker/.env"
    if not env.exists():
        env.write_text("COMPOSE_PROFILES=weaviate,postgresql,collaboration\nEXPOSE_NGINX_PORT=8088\nEXPOSE_NGINX_SSL_PORT=8448\nDIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN=" + secrets.token_hex(32) + "\nSECRET_KEY=" + secrets.token_hex(32) + "\n")
        env.chmod(0o600)
    current = env.read_text()
    for name in ("DB_PASSWORD", "REDIS_PASSWORD", "PLUGIN_DAEMON_KEY", "PLUGIN_DIFY_INNER_API_KEY", "WEAVIATE_API_KEY"):
        if not any(line.startswith(name + "=") for line in current.splitlines()):
            current += name + "=" + secrets.token_hex(32) + "\n"
    if "SSRF_PROXY_ALLOW_PRIVATE_DOMAINS=" not in current:
        current += "SSRF_PROXY_ALLOW_PRIVATE_DOMAINS=host.docker.internal\n"
    if "CODE_EXECUTION_API_KEY=" not in current:
        current += "CODE_EXECUTION_API_KEY=" + secrets.token_hex(32) + "\n"
    if not any(line.startswith("SANDBOX_API_KEY=") for line in current.splitlines()):
        execution_key = next(line.split("=", 1)[1] for line in current.splitlines() if line.startswith("CODE_EXECUTION_API_KEY="))
        current += "SANDBOX_API_KEY=" + execution_key + "\n"
    for name, value in {"CODE_MAX_STRING_LENGTH": "12000000", "HTTP_REQUEST_NODE_MAX_TEXT_SIZE": "12000000"}.items():
        if not any(line.startswith(name + "=") for line in current.splitlines()):
            current += name + "=" + value + "\n"
    env.write_text(current)
    env.chmod(0o600)
    (private / "compose.override.yml").write_text("services:\n  nginx:\n    ports: !override\n      - '127.0.0.1:8088:80'\n      - '127.0.0.1:8448:443'\n  api:\n    extra_hosts: ['host.docker.internal:host-gateway']\n  worker:\n    extra_hosts: ['host.docker.internal:host-gateway']\n  ssrf_proxy:\n    extra_hosts: ['host.docker.internal:host-gateway']\n  plugin_daemon:\n    ports: !override []\n")
    (private / "version.json").write_text(json.dumps({"version": VERSION, "git_sha": tree["sha"]}, indent=2))
    print(f"Prepared official Dify {VERSION}: {len(docker_files)} files at {destination}")
    print("Private tool token saved; its value was not printed.")


def doctor():
    free = shutil.disk_usage(ROOT).free // (1024 ** 3)
    print(f"disk_free_gib={free}")
    docker = shutil.which("docker")
    if not docker:
        print("BLOCKED: Docker Engine / Compose not installed. Run the reviewed administrator setup in dify/install-docker.sh.")
        return 2
    result = subprocess.run([docker, "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True)
    if result.returncode:
        print("BLOCKED: Docker daemon inaccessible to the current user.")
        return 2
    print("docker=" + result.stdout.strip())
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "doctor"])
    options = parser.parse_args()
    if options.action == "prepare":
        prepare()
    else:
        raise SystemExit(doctor())
