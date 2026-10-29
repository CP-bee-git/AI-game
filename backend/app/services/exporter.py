import html
import json
from collections.abc import Mapping


LABELS = {
    "job_title": "目标岗位",
    "company": "用人单位",
    "strengths": "简历优势",
    "must_fix": "优先改进",
    "optional_improve": "进一步优化",
    "ats_keywords": "岗位关键词",
    "checklist": "投递前检查",
    "status": "面试状态",
    "current_question": "当前问题",
    "turns": "问答记录",
    "overall_score": "平均评分（5分制）",
    "summary": "面试总结",
    "notice": "数据说明",
    "engine": "生成方式",
    "sequence": "题号",
    "question": "问题",
    "answer": "回答",
    "score": "评分",
    "feedback": "反馈",
}


def _value_html(value: object) -> str:
    if isinstance(value, Mapping):
        return "<dl>" + "".join(
            f"<dt>{html.escape(LABELS.get(key, str(key)))}</dt><dd>{_value_html(item)}</dd>" for key, item in value.items()
        ) + "</dl>"
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{_value_html(item)}</li>" for item in value) + "</ul>"
    return f"<p>{html.escape(str(value))}</p>"


def render_export(data: Mapping, export_type: str, output_format: str) -> tuple[str, str, str]:
    filename = f"careerpilot-{export_type}.{output_format}"
    if output_format == "json":
        return filename, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False, indent=2)
    title = "简历诊断报告" if export_type == "diagnosis" else "模拟面试反馈"
    sections = []
    for key, value in data.items():
        if key in {"report_id", "session_id"}:
            continue
        if key == "engine":
            value = {"model": "千问云 API", "rules": "规则演示"}.get(str(value), value)
        label = html.escape(LABELS.get(key, str(key)))
        sections.append(f"<section><h2>{label}</h2>{_value_html(value)}</section>")
    document = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f7f6;color:#1c2a31;font:15px/1.75 Arial,"Microsoft YaHei",sans-serif}}main{{max-width:900px;margin:36px auto;padding:46px 54px;background:#fff;border-top:5px solid #087f78;box-shadow:0 8px 30px #173b3510}}header{{padding-bottom:24px;border-bottom:1px solid #dce5e2}}header p{{color:#64756f;font-size:12px}}h1{{margin:0 0 5px;font-size:28px}}h2{{margin:0 0 10px;color:#075e5a;font-size:16px}}section{{padding:20px 0;border-bottom:1px solid #e8eeec}}p{{margin:5px 0}}ul{{margin:7px 0;padding-left:22px}}li{{margin:5px 0}}dl{{display:grid;grid-template-columns:140px 1fr;gap:5px 14px}}dt{{font-weight:700;color:#52645f}}dd{{margin:0}}.notice{{padding:12px 14px;background:#edf6f3;color:#285e56;border-left:3px solid #64a79a;font-size:12px}}@media print{{body{{background:#fff}}main{{max-width:none;margin:0;padding:12mm 14mm;box-shadow:none}}}}
</style><body><main><header><h1>{title}</h1><p>CareerPilot · 求职辅助工作区</p></header>{''.join(sections)}</main></body></html>"""
    return filename, "text/html; charset=utf-8", document

