"""Explainable skill matches using China's official occupation names and codes.

The project supplies work summaries, common job titles and matching keywords;
none of those are official qualification requirements or official skill ratings.
"""

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.services.matching import normalize


SCORING_METHOD = "项目规则分=60%已对应技能数÷用户技能数（至少3项为基数）＋40%证据广度（6项封顶）；全部关键词等权，同义词合并为1项。关键词、场景说明与排序由项目维护，不是国家职业标准、资格条件或官方评分；星级为规则分÷20后四舍五入。"

# Exact aliases only: a single-letter skill such as R never matches a word fragment.
SKILL_ALIASES = {
    "Python": ("Python3", "Python开发", "Python编程"),
    "SQL": ("Structured query language SQL", "SQL查询", "结构化查询语言"),
    "Java": ("Oracle Java", "Java开发"),
    "JavaScript": ("JS",),
    "TypeScript": ("TS",),
    "HTML": ("HTML5", "Hypertext markup language HTML"),
    "CSS": ("CSS3", "Cascading style sheets CSS"),
    "Excel": ("Microsoft Excel", "电子表格"),
    "Word": ("Microsoft Word",),
    "PowerPoint": ("PPT", "Microsoft PowerPoint"),
    "Office": ("办公软件", "Microsoft Office software"),
    "Power BI": ("PowerBI", "Microsoft Power BI"),
    "SPSS": ("IBM SPSS Statistics",),
    "MATLAB": ("The MathWorks MATLAB",),
    "Photoshop": ("PS", "Adobe Photoshop"),
    "Illustrator": ("Adobe Illustrator",),
    "InDesign": ("Adobe InDesign",),
    "Premiere": ("PR", "Adobe Premiere Pro"),
    "After Effects": ("AE", "Adobe After Effects"),
    "AutoCAD": ("CAD",),
    "ArcGIS": ("ESRI ArcGIS software",),
    "Node.js": ("Nodejs",),
    "React": ("React.js", "Reactjs"),
    "REST API": ("RESTful API", "RESTful"),
    "机器学习": ("Machine Learning",),
    "深度学习": ("Deep Learning",),
    "数据分析": ("Data analysis software",),
    "数据可视化": ("可视化",),
    "数据清洗": ("数据预处理",),
    "统计学": ("统计分析",),
    "用户研究": ("用户调研",),
    "需求分析": ("业务需求分析",),
    "沟通": ("表达沟通", "口头表达", "沟通表达"),
    "组织协调": ("协调",),
    "写作": ("文案写作", "文字表达"),
    "教学": ("授课", "讲课"),
    "客户服务": ("客服",),
    "招聘": ("人才招聘",),
    "会计核算": ("账务处理",),
    "电商运营": ("电子商务运营",),
    "新媒体运营": ("内容运营",),
}
_ALIAS_INDEX = {normalize(alias): normalize(name) for name, aliases in SKILL_ALIASES.items() for alias in (name, *aliases)}


def _canonical(value: str) -> str:
    normalized = normalize(value)
    return _ALIAS_INDEX.get(normalized, normalized)


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    path = Path(__file__).resolve().parents[1] / "data" / "occupations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def career_matches(profile: dict, limit: int = 10) -> dict:
    """Return up to ten Chinese occupations, ranked by explicit skill evidence."""
    snapshot = _snapshot()
    display = {}
    for item in profile.get("skills", []):
        value = item if isinstance(item, str) else (item.get("normalized_name") or item.get("name")) if isinstance(item, dict) else None
        if isinstance(value, str) and value.strip() and _canonical(value):
            display.setdefault(_canonical(value), value.strip())
    candidates = set(display)
    scored = []
    for occupation in snapshot["occupations"]:
        keyword_names = {_canonical(keyword): keyword for keyword in occupation["keywords"]}
        matched_names = candidates & keyword_names.keys()
        supported = len(matched_names)
        score = round(60 * supported / max(len(candidates), 3) + 40 * min(supported / 6, 1), 1) if candidates else 0.0
        matched = [display[name] for name in sorted(matched_names)]
        gaps = [keyword for name, keyword in keyword_names.items() if name not in candidates][:5]
        reason = (
            f"你填写的 {len(candidates)} 项技能中，有 {supported} 项与本项目为该职业整理的关键词对应：{'、'.join(matched)}。"
            if matched else "目前没有对应的技能证据，记为 0 分。可先阅读工作方向说明，再补充确实掌握的技能。"
        )
        scored.append({
            "code": occupation["code"],
            "title": occupation["title"],
            "category": occupation["category"],
            "typical_jobs": occupation["typical_jobs"],
            "description": occupation["description"],
            "source_url": occupation["source_url"],
            "source_title": snapshot["catalog"]["source_title"],
            "official_classification": occupation["official_classification"],
            "score": score,
            "stars": min(5, int(score / 20 + .5)),
            "matched_skills": matched,
            "skill_gaps": gaps,
            "reason": reason,
        })
    # Equal scores rotate between domains, without reordering unequal scores.
    by_score = defaultdict(list)
    for result in scored:
        by_score[result["score"]].append(result)
    ordered = []
    for score in sorted(by_score, reverse=True):
        categories = defaultdict(list)
        for result in by_score[score]:
            categories[result["category"]].append(result)
        for index in range(max(map(len, categories.values()))):
            ordered.extend(items[index] for items in categories.values() if index < len(items))
    return {"catalog": {**snapshot["catalog"], "scoring_method": SCORING_METHOD}, "total": len(scored), "results": ordered[:max(1, min(int(limit), 10))]}
