import html
import json
from collections.abc import Mapping


def render_export(data: Mapping, export_type: str, output_format: str) -> tuple[str, str, str]:
    filename = f"careerpilot-{export_type}.{output_format}"
    if output_format == "json":
        return filename, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False, indent=2)
    title = "简历诊断报告" if export_type == "diagnosis" else "模拟面试反馈"
    sections = []
    for key, value in data.items():
        if key in {"report_id", "session_id"}:
            continue
        label = html.escape(str(key))
        if isinstance(value, list):
            body = "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in value) + "</ul>"
        else:
            body = f"<p>{html.escape(str(value))}</p>"
        sections.append(f"<section><h2>{label}</h2>{body}</section>")
    document = f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>{title}</title><body><h1>{title}</h1>{''.join(sections)}</body></html>"
    return filename, "text/html; charset=utf-8", document

