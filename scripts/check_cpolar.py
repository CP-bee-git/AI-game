"""Run with python3 scripts/check_cpolar.py; no account or network is needed."""

from html import escape
import json

from manage import cpolar_urls


url = "https://example.cpolar.cn"
state = {"Txns": [], "UiState": {"Tunnels": [{"PublicUrl": "http://example.cpolar.cn"}, {"PublicUrl": url}]}}
html = "<script>window.data = JSON.parse(" + json.dumps(json.dumps(state)) + ");</script>"
assert cpolar_urls(html) == [url]
assert cpolar_urls(escape(html)) == [url]
assert cpolar_urls(json.dumps({"tunnels": [{"public_url": url}]})) == [url]
for invalid in ("", "<html>offline</html>", 'window.data = JSON.parse("invalid");', 'window.data = JSON.parse(alert("no"));', "[]", '{"UiState":null}', '{"tunnels":42}'):
    assert cpolar_urls(invalid) == [], invalid
print("cpolar inspector parsing checks passed")
