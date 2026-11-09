import base64
import http.cookiejar
import json
from pathlib import Path
import secrets
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8088"


def main():
    private = ROOT / ".private/dify"
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    account_file = private / "admin.json"
    if account_file.exists():
        account = json.loads(account_file.read_text())
    else:
        account = {"email": "admin@careerpilot.local", "name": "CareerPilot", "password": "Cp9" + secrets.token_urlsafe(24), "language": "zh-Hans"}
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(path: str, payload: dict | None = None):
        headers = {"Content-Type": "application/json", "Origin": BASE, "Referer": BASE + "/signin"}
        token = next((cookie.value for cookie in jar if "csrf" in cookie.name.lower()), "")
        if token:
            headers["X-CSRF-Token"] = token
        data = json.dumps(payload).encode() if payload is not None else None
        remote = urllib.request.Request(BASE + "/console/api" + path, data=data, headers=headers)
        with opener.open(remote, timeout=40) as response:
            return json.load(response)

    setup = request("/setup")
    if setup["step"] == "not_started":
        if not account_file.exists():
            account_file.write_text(json.dumps(account, ensure_ascii=False, indent=2))
            account_file.chmod(0o600)
        request("/setup", account)
        print("Administrator initialized; credentials saved privately")
    elif not account_file.exists():
        raise SystemExit("Dify already initialized; existing administrator credentials required. No password was changed.")
    result = request("/login", {"email": account["email"], "password": base64.b64encode(account["password"].encode()).decode(), "remember_me": True})
    if result.get("result") != "success":
        raise SystemExit("Dify login did not succeed; private credentials were not displayed")
    session = {"cookie": "; ".join(cookie.name + "=" + cookie.value for cookie in jar),
               "csrf_token": next((cookie.value for cookie in jar if "csrf" in cookie.name.lower()), "")}
    if not session["csrf_token"]:
        raise SystemExit("Dify did not set a CSRF cookie")
    session_file = private / "console-session.json"
    session_file.write_text(json.dumps(session))
    session_file.chmod(0o600)
    print("Administrator login verified; console session stored privately")


if __name__ == "__main__":
    main()
