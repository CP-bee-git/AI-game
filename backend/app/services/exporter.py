"""Portable, printable reports with no remote fonts, scripts or image assets."""

import html
import json
import math
from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo


LABELS = {
    "strengths": "已有优势", "must_fix": "优先完善", "optional_improve": "表达与内容优化",
    "ats_keywords": "岗位关键词", "checklist": "投递前检查", "summary": "面试复盘",
}


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _list(items: object, empty: str = "暂无补充项") -> str:
    if not isinstance(items, list) or not items:
        return f'<p class="muted">{_escape(empty)}</p>'
    return '<ul class="item-list">' + "".join(f'<li>{_escape(item)}</li>' for item in items) + '</ul>'


def _stars(value: object) -> str:
    try:
        score = float(value)
        score = max(0.0, min(5.0, score)) if math.isfinite(score) else 0
    except (ValueError, TypeError):
        score = 0
    rounded = math.floor(score + 0.5)
    return (f'<span class="star-rating" role="img" aria-label="{score:g} / 5 星">'
            f'<span aria-hidden="true">{"★" * rounded}<span class="empty-stars">{"☆" * (5-rounded)}</span></span>'
            f'<span class="star-value">{score:g}<small> / 5</small></span></span>')


def _section(number: str, title: str, content: str, css_class: str = "") -> str:
    return f'<section class="report-section {css_class}"><div class="section-title"><span>{number}</span><h2>{_escape(title)}</h2></div>{content}</section>'


def _radar(dimensions: list[Mapping]) -> str:
    selected = dimensions[:5]
    if len(selected) != 5:
        return ""
    cx, cy, radius = 160, 140, 87

    def point(index: int, scale: float = 1.0) -> str:
        angle = -math.pi / 2 + index * 2 * math.pi / 5
        return f'{cx + radius * scale * math.cos(angle):.1f},{cy + radius * scale * math.sin(angle):.1f}'

    grid = ''.join(f'<polygon points="{" ".join(point(i, level/5) for i in range(5))}" class="radar-grid" />' for level in range(1, 6))
    spokes = ''.join(f'<line x1="{cx}" y1="{cy}" x2="{point(i).split(",")[0]}" y2="{point(i).split(",")[1]}" class="radar-axis" />' for i in range(5))
    values, labels = [], []
    for i, dimension in enumerate(selected):
        score = max(0, min(5, float(dimension.get('score', 0))))
        values.append(point(i, score / 5))
        x, y = point(i, 1.31).split(',')
        labels.append(f'<text x="{x}" y="{float(y)+4:.1f}" text-anchor="middle">{_escape(dimension.get("name", ""))}</text>')
    return (f'<svg class="radar" viewBox="0 0 320 280" role="img" aria-label="五维画像证据完整度星图，具体分值见右侧星级列表">'
            f'{grid}{spokes}<polygon points="{" ".join(values)}" class="radar-fill" />{"".join(labels)}</svg>')


def _analysis(data: Mapping) -> str:
    dimensions = data.get('dimensions', [])
    if not isinstance(dimensions, list):
        return ""
    dimensions = [item for item in dimensions if isinstance(item, Mapping)]
    if not dimensions:
        return ""
    rows = []
    for dimension in dimensions:
        quote = dimension.get('evidence', [])
        evidence = ''.join(f'<blockquote>{_escape(item)}</blockquote>' for item in quote[:2]) if isinstance(quote, list) else ''
        rows.append(f'<div class="dimension"><div class="dimension-heading"><h3>{_escape(dimension.get("name"))}</h3>{_stars(dimension.get("score"))}</div><p class="dimension-note">{_escape(dimension.get("note", ""))}</p>{evidence}</div>')
    return f'<p class="explanation">{_escape(data.get("notice", "每颗星对应一项可核对的信息或证据，不表示能力水平。"))}</p><div class="profile-grid"><div class="radar-panel">{_radar(dimensions)}<p class="radar-caption">五星制 · 资料与证据完整度</p></div><div>{"".join(rows)}</div></div>'


def _careers(data: Mapping) -> str:
    catalog = data.get('catalog', {})
    catalog = catalog if isinstance(catalog, Mapping) else {}
    items = data.get('results', [])
    items = items if isinstance(items, list) else []
    rows = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, Mapping):
            continue
        matched = item.get('matched_skills') or []
        gaps = item.get('skill_gaps') or []
        source_url = str(item.get('source_url', ''))
        source = f'<a href="{_escape(source_url)}" target="_blank" rel="noreferrer">职业来源 ↗</a>' if source_url.startswith('https://') else ''
        rows.append(f'''<article class="career-card"><div class="career-heading"><span class="rank">{index:02d}</span><div><h3>{_escape(item.get('title'))}</h3><p class="career-original">{_escape(item.get('original_title'))} · {_escape(item.get('code'))}</p></div><div class="career-score">{_escape(item.get('score', 0))}<small>匹配分 / 100</small></div></div><details class="career-definition"><summary>职业定义原文</summary><p lang="en">{_escape(item.get('description'))}</p></details><p class="career-reason">{_escape(item.get('reason'))}</p><div class="career-evidence"><p><b>已命中</b> {_escape('、'.join(str(v) for v in matched) or '暂无直接技能证据')}</p><p><b>待核对</b> {_escape('、'.join(str(v) for v in gaps) or '本条目所列技能暂无缺口')}</p></div><div class="career-foot">{_stars(item.get('stars', 0))}<span>{source}</span></div></article>''')
    attribution = f'{catalog.get("name", "职业库")} · {catalog.get("version", "")} · {catalog.get("license", "")} · 数据核对 {catalog.get("accessed_on", "")}'
    source_url = str(catalog.get('source_url', ''))
    source = f'<p class="source-url">{_escape(source_url)}</p>' if source_url.startswith('https://') else ''
    credit = f'<p lang="en">{_escape(catalog.get("attribution", ""))}</p>'
    return f'<p class="explanation">{_escape(catalog.get("notice", "职业方向匹配，不是实时招聘职位或录用建议。"))}</p><div class="career-list">{"".join(rows)}</div><aside class="source-note"><b>数据来源与许可</b><p>{_escape(attribution)}</p>{source}{credit}<p>{_escape(catalog.get("scoring_method", ""))}</p></aside>'


def _interview(data: Mapping) -> str:
    rows = []
    turns = data.get('turns') or []
    for index, turn in enumerate(turns, 1):
        if not isinstance(turn, Mapping):
            continue
        rating = _stars(turn['score']) if turn.get('score') is not None else '<span class="muted">尚未评分</span>'
        rows.append(f'<article class="turn-card"><div class="turn-head"><span class="turn-label">QUESTION {index:02d}</span>{rating}</div><h3>{_escape(turn.get("question"))}</h3><div class="answer"><span class="small-label">我的回答</span><p>{_escape(turn.get("answer") or "尚未回答")}</p></div><div class="feedback"><span class="small-label">练习反馈</span><p>{_escape(turn.get("feedback") or "完成回答后生成反馈")}</p></div></article>')
    if data.get('current_question'):
        rows.append(f'<article class="turn-card pending"><span class="small-label">下一道练习题</span><h3>{_escape(data["current_question"])}</h3><p class="muted">此题尚未回答，不计入评分。</p></article>')
    return '<div class="turn-list">' + ''.join(rows) + '</div>'


STYLES = """
:root{color-scheme:light;--ink:#20232d;--muted:#717682;--line:#e6e7eb;--accent:#5654c7;--paper:#fff}*{box-sizing:border-box}body{margin:0;background:#f1f2f5;color:var(--ink);font:14px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;overflow-wrap:anywhere}main{max-width:1020px;margin:32px auto;background:var(--paper);box-shadow:0 12px 60px #2427440b}.toolbar{max-width:1020px;margin:24px auto -16px;text-align:right;color:var(--muted);font-size:12px}.toolbar button{font:inherit;color:var(--ink);background:#fff;border:1px solid #dcdde4;border-radius:6px;padding:8px 14px;cursor:pointer}.report-header{padding:42px 56px 36px;border-top:4px solid var(--ink);border-bottom:1px solid var(--line)}.brand-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:40px}.wordmark{font-weight:750;font-size:19px;letter-spacing:-.5px}.brand-tag{font-size:10px;letter-spacing:2px;color:var(--muted);margin-left:10px}.edition{font-size:11px;color:var(--muted)}.kicker{font-size:10px;letter-spacing:3px;color:var(--accent);font-weight:650;margin:0 0 10px}h1{font-size:32px;font-weight:700;letter-spacing:-1px;line-height:1.4;margin:0 0 14px}.subtitle{font-size:15px;color:var(--muted);margin:0}.meta{display:flex;gap:26px;flex-wrap:wrap;margin-top:28px;font-size:12px;color:var(--muted)}.meta b{display:block;font-weight:550;color:var(--ink)}.report-body{padding:8px 56px 36px}.report-section{padding:28px 0;border-bottom:1px solid var(--line)}.section-title{display:flex;gap:13px;align-items:center;margin-bottom:18px}.section-title>span{font-size:11px;color:var(--accent);font-weight:700;letter-spacing:1px}h2{font-size:18px;line-height:1.5;letter-spacing:-.3px;margin:0}h3{font-size:14px;margin:0;font-weight:650}p{margin:8px 0}.muted,.explanation{color:var(--muted)}.explanation{font-size:12px;line-height:1.9;margin:0 0 20px}.item-list{list-style:none;padding:0;margin:0;counter-reset:item}.item-list li{position:relative;padding:11px 0 11px 24px;border-bottom:1px solid #f0f0f3;white-space:pre-line}.item-list li:last-child{border-bottom:0}.item-list li:before{content:"";width:5px;height:5px;background:var(--accent);position:absolute;left:3px;top:22px;border-radius:50%}.priority .item-list li:before{background:#b7884a}.checklist .item-list li:before{width:10px;height:10px;background:none;border:1px solid #a4a7b2;top:18px;border-radius:2px}.tags{display:flex;gap:8px;flex-wrap:wrap}.tag{background:#f5f5fa;border:1px solid #e6e5f1;color:#55566f;border-radius:4px;padding:4px 10px;font-size:12px}.profile-grid{display:grid;grid-template-columns:275px 1fr;gap:30px;align-items:start}.radar-panel{position:sticky;top:20px}.radar{width:100%;max-width:320px;display:block}.radar-grid{fill:none;stroke:#dedfea;stroke-width:1}.radar-axis{stroke:#e5e5ee;stroke-width:1}.radar-fill{fill:#6260c824;stroke:#6260c8;stroke-width:2}.radar text{font-size:11px;fill:#676b78}.radar-caption{font-size:10px;text-align:center;color:var(--muted);letter-spacing:1px}.dimension{padding:13px 0;border-bottom:1px solid #eeeef3}.dimension:first-child{padding-top:0}.dimension-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.star-rating{display:inline-flex;align-items:center;gap:10px;white-space:nowrap;color:#b18a45;font-size:16px;letter-spacing:1px}.empty-stars{color:#c7c8d1}.star-value{font-size:12px;letter-spacing:0;color:var(--ink);font-variant-numeric:tabular-nums}.star-value small{color:var(--muted);font-weight:400;font-size:10px}.dimension-note{font-size:11px;color:var(--muted);line-height:1.8}.dimension blockquote{margin:8px 0 0;padding:6px 12px;border-left:2px solid #d9d7ed;color:#606474;font-size:11px;line-height:1.8}.career-list{display:grid;grid-template-columns:1fr 1fr;gap:15px}.career-card{padding:20px;border:1px solid var(--line);border-radius:5px;break-inside:avoid-page;page-break-inside:avoid}.career-heading{display:flex;align-items:flex-start;gap:10px}.rank{color:var(--accent);font-size:11px;font-weight:650;padding-top:2px}.career-original{font-size:9px;color:var(--muted);margin:2px 0 12px;line-height:1.5}.career-score{margin-left:auto;font-size:20px;line-height:1.3;font-weight:650;white-space:nowrap;font-variant-numeric:tabular-nums}.career-score small{display:block;font-size:8px;font-weight:400;color:var(--muted)}.career-card>p{font-size:11px;line-height:1.9}.career-reason{color:var(--muted)}.career-evidence{font-size:10px;color:#696d79;border-top:1px solid #eeeef3;padding-top:8px}.career-evidence b{font-weight:550;color:#3d414f}.career-foot{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:13px}.career-foot>span:last-child{font-size:8px;color:var(--muted)}.career-foot .star-rating{font-size:12px;gap:6px}.source-note,.data-note{margin-top:22px;padding:14px 16px;background:#f7f7fa;color:#686c7a;font-size:11px;line-height:1.9;border-left:2px solid #d9d8e6}.source-url{font-size:9px}.turn-list{display:grid;gap:20px}.turn-card{border:1px solid var(--line);padding:22px 25px;border-radius:5px}.turn-head{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:14px}.turn-label,.small-label{font-size:9px;letter-spacing:1px;color:var(--muted);font-weight:650}.turn-label{color:var(--accent)}.turn-card h3{font-size:15px;line-height:1.9;margin-bottom:17px}.answer,.feedback{padding:12px 15px;background:#f7f7fa;margin-top:10px;border-radius:3px}.answer p,.feedback p{font-size:12px;white-space:pre-wrap;margin:4px 0}.feedback{background:#f5f5fb;border-left:2px solid #d9d7ed}.pending{border-style:dashed}.score-banner{display:flex;align-items:center;gap:25px;padding:18px 22px;background:#f7f7fa}.score-banner strong{font-size:31px;line-height:1.1;color:var(--accent)}.score-banner small{font-size:13px;font-weight:400;color:var(--muted)}.score-banner p{font-size:11px;color:var(--muted);margin:0}.report-footer{padding:22px 56px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:9px;letter-spacing:.3px}@media(max-width:700px){body{font-size:13px}main{margin:12px}.toolbar{margin:12px 12px 0}.report-header{padding:26px 24px}.report-body{padding:0 24px 24px}.report-footer{padding:20px 24px;display:block}.brand-row{margin-bottom:28px}.brand-tag{display:none}h1{font-size:26px}.profile-grid{grid-template-columns:1fr;gap:16px}.radar-panel{position:static;max-width:300px;margin:auto}.career-list{grid-template-columns:1fr}.meta{gap:16px}.turn-card{padding:18px}.turn-head{gap:8px}.edition{font-size:9px}}@page{size:A4;margin:12mm}@media print{body{background:#fff;font-size:10pt;-webkit-print-color-adjust:exact;print-color-adjust:exact}main{max-width:none;margin:0;box-shadow:none}.toolbar{display:none}.report-header{padding:12mm 7mm 8mm}.report-body{padding:0 7mm 7mm}.report-footer{padding:5mm 7mm;font-size:8pt}.report-section{padding:6mm 0}h2,h3{break-after:avoid-page}p,li{orphans:3;widows:3}.radar-panel{position:static}.dimension,.score-banner,.source-note{break-inside:avoid-page}.career-list{display:block;columns:2;column-gap:4mm}.career-card{display:inline-block;width:100%;margin:0 0 4mm;padding:4mm}.turn-card{padding:5mm;box-decoration-break:clone;-webkit-box-decoration-break:clone}.brand-row{margin-bottom:8mm}.profile-grid{grid-template-columns:62mm 1fr;gap:5mm}.dimension-note{font-size:8pt}.explanation{font-size:8.5pt}.report-footer{break-inside:avoid-page}}
@media print{.career-report{break-before:page}.report-header{padding:5mm 7mm 4mm}.brand-row{margin-bottom:4mm}h1{font-size:23pt}.kicker{margin-bottom:3mm}.meta{margin-top:4mm}.report-section{padding:4mm 0}.section-title{margin-bottom:3mm}.profile-grid{grid-template-columns:54mm 1fr;gap:5mm}.dimension{padding:2mm 0}.dimension-note{margin:1mm 0;font-size:8pt;line-height:1.55}.dimension blockquote{font-size:7.5pt;line-height:1.5;margin:1mm 0 0;padding:1mm 2mm}.dimension blockquote+blockquote{display:none}.career-list{display:grid;grid-template-columns:1fr 1fr;gap:3mm;columns:auto}.career-card{display:block;margin:0;padding:3mm}.career-card>p{font-size:8pt}.career-definition{font-size:8pt;color:var(--muted)}.career-evidence{font-size:7.5pt}.source-note,.data-note{font-size:7.5pt;line-height:1.6;padding:3mm;margin-top:3mm}}
"""


def render_export(data: Mapping, export_type: str, output_format: str) -> tuple[str, str, str]:
    filename = f"careerpilot-{export_type}.{output_format}"
    if output_format == "json":
        return filename, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False, indent=2)
    titles = {'profile': '职业画像与发展方向', 'diagnosis': '简历诊断报告', 'interview': '模拟面试反馈'}
    title = titles.get(export_type, '求职分析报告')
    sections = []
    analysis = data if export_type == 'profile' else data.get('profile_analysis')
    if isinstance(analysis, Mapping) and analysis.get('dimensions'):
        sections.append(_section(f'{len(sections)+1:02d}', '五维画像 · 证据完整度', _analysis(analysis)))
    if export_type == 'profile':
        careers = data.get('careers')
        if isinstance(careers, Mapping):
            sections.append(_section(f'{len(sections)+1:02d}', '十个具体职业方向', _careers(careers), 'career-report'))
        if data.get('data_notice'):
            sections.append(f'<aside class="data-note"><b>画像数据说明</b><p>{_escape(data["data_notice"])}</p></aside>')
    elif export_type == 'interview':
        score = data.get('overall_score')
        if score is not None:
            overview = f'<div class="score-banner"><strong>{_escape(score)}<small> / 5</small></strong><div>{_stars(score)}<p>仅为模拟练习反馈，不表示面试通过率或实际职业能力。</p></div></div>'
            sections.append(_section(f'{len(sections)+1:02d}', '本次练习概览', overview))
        sections.append(_section(f'{len(sections)+1:02d}', '逐题回答与反馈', _interview(data)))
        sections.append(_section(f'{len(sections)+1:02d}', LABELS['summary'], _list(data.get('summary'))))
    else:
        for key in ('strengths', 'must_fix', 'optional_improve', 'ats_keywords', 'checklist'):
            value = data.get(key)
            body = '<div class="tags">' + ''.join(f'<span class="tag">{_escape(item)}</span>' for item in value) + '</div>' if key == 'ats_keywords' and isinstance(value, list) else _list(value)
            css = 'priority' if key == 'must_fix' else 'checklist' if key == 'checklist' else ''
            sections.append(_section(f'{len(sections)+1:02d}', LABELS[key], body, css))
    if export_type != 'profile' and data.get('notice'):
        sections.append(f'<aside class="data-note"><b>数据与生成方式说明</b><p>{_escape(data["notice"])}</p></aside>')
    engine = {'model': '千问云 API + 规则核对', 'rules': '规则演示'}.get(str(data.get('engine')), '已确认画像 · 规则核对')
    if export_type == "profile" and "合成" in str(data.get("data_notice", "")):
        engine = "合成样例 · 规则分析"
    status = {'active': '练习进行中', 'completed': '练习已完成'}.get(str(data.get('status')), '个人求职参考')
    subtitle = ' · '.join(str(data.get(key)) for key in ('job_title', 'company') if data.get(key)) or '以简历证据为起点，梳理职业发展的下一步。'
    date = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y.%m.%d')
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light"><title>{title} · CareerPilot</title><style>{STYLES}</style></head><body><div class="toolbar"><button type="button" onclick="window.print()">打印 / 保存为 PDF</button></div><main><header class="report-header"><div class="brand-row"><div class="wordmark">CareerPilot<span class="brand-tag">就业罗盘</span></div><span class="edition">PERSONAL CAREER REPORT · {date}</span></div><p class="kicker">EVIDENCE · REFLECTION · NEXT STEP</p><h1>{title}</h1><p class="subtitle">{_escape(subtitle)}</p><div class="meta"><div>分析方式<b>{_escape(engine)}</b></div><div>报告用途<b>{_escape(status)}</b></div><div>阅读提示<b>先核对事实，再采用建议</b></div></div></header><div class="report-body">{''.join(sections)}</div><footer class="report-footer"><span>CareerPilot · 就业罗盘</span><span>资料与自述未经第三方核验。职业方向与练习反馈仅供本人参考。</span></footer></main></body></html>'''
    return filename, 'text/html; charset=utf-8', document
