import argparse
import json
from pathlib import Path
import urllib.request
from urllib.error import HTTPError

from build_dify_workflows import OPERATIONS, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--session-file", type=Path, required=True)
    args = parser.parse_args()
    session = json.loads(args.session_file.read_text())
    private = ROOT / ".private/dify"
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    credentials = dict(line.split("=", 1) for line in (private / "tools.env").read_text().splitlines() if "=" in line)
    headers = {"Content-Type": "application/json", "Cookie": session["cookie"], "X-CSRF-Token": session["csrf_token"], "Origin": args.base_url, "Referer": args.base_url + "/apps"}

    def request(path, payload):
        remote = urllib.request.Request(args.base_url + "/console/api" + path, method="POST", data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(remote, timeout=45) as response:
            return json.load(response)

    keys_file, apps_file = private / "app-keys.json", private / "apps.json"
    keys = json.loads(keys_file.read_text()) if keys_file.exists() else {}
    apps = json.loads(apps_file.read_text()) if apps_file.exists() else {}
    for operation in OPERATIONS:
        if operation in keys:
            print(operation, "already configured; skipped")
            continue
        if operation not in apps:
            document = json.loads((ROOT / "dify/workflows" / f"{operation}.yml").read_text())
            for variable in document["workflow"]["environment_variables"]:
                if variable["name"] == "AGENT_TOOLS_TOKEN":
                    variable["value"] = credentials["AGENT_TOOLS_TOKEN"]
            result = request("/apps/imports", {"mode": "yaml-content", "yaml_content": json.dumps(document, ensure_ascii=False)})
            if result.get("status") not in {"completed", "completed-with-warnings"} or not result.get("app_id"):
                raise SystemExit(f"{operation}: import did not complete; inspect the Dify console before retrying")
            apps[operation] = result["app_id"]
            apps_file.write_text(json.dumps(apps, indent=2))
            apps_file.chmod(0o600)
        app_id = apps[operation]
        request(f"/apps/{app_id}/workflows/publish", {"marked_name": "CareerPilot", "marked_comment": "Local multi-agent workflow"})
        result = request(f"/apps/{app_id}/api-keys", {})
        if not isinstance(result.get("token"), str) or not result["token"]:
            raise SystemExit(f"{operation}: no API token returned; inspect API access in the console")
        keys[operation] = result["token"]
        keys_file.write_text(json.dumps(keys, indent=2))
        keys_file.chmod(0o600)
        print(operation, "imported and published; app key stored privately")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as failure:
        raise SystemExit(f"Dify console HTTP {failure.code}; check login session / CSRF / version. Response body omitted to protect credentials.") from None
