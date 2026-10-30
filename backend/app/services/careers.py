"""Explainable matches against a packaged, attributed O*NET occupation snapshot."""

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.services.matching import normalize, skill_names


SCORING_METHOD = "规则分=60%对应技能比例（至少3项为基数）＋40%证据广度（6项封顶）；基本/可迁移技能按官方重要性÷5加权，软件按 in-demand / hot / 其他分别加权1 / 0.75 / 0.5。星级为规则分÷20后四舍五入。"


# Project translations and exact aliases, not additional O*NET requirements.
# Deliberately no fuzzy substring matches: "R" must not match every English word.
SKILL_ALIASES = {
    "Reading Comprehension": ("阅读理解", "文献阅读"),
    "Active Listening": ("积极倾听", "倾听"),
    "Writing": ("写作", "文案写作", "技术写作"),
    "Speaking": ("口头表达", "表达沟通", "沟通"),
    "Mathematics": ("数学", "数学建模", "统计学"),
    "Science": ("科学方法", "科学研究"),
    "Critical Thinking": ("批判性思维", "逻辑思维"),
    "Active Learning": ("主动学习", "学习能力"),
    "Learning Strategies": ("学习策略",),
    "Monitoring": ("监测", "过程监控"),
    "Social Perceptiveness": ("社会洞察", "人际洞察"),
    "Coordination": ("协调", "组织协调"),
    "Persuasion": ("说服", "说服沟通"),
    "Negotiation": ("谈判", "商务谈判"),
    "Instructing": ("教学", "授课", "培训"),
    "Service Orientation": ("服务意识", "客户服务"),
    "Complex Problem Solving": ("复杂问题解决", "问题解决"),
    "Operations Analysis": ("需求分析", "业务需求分析"),
    "Technology Design": ("技术设计",),
    "Equipment Selection": ("设备选型",),
    "Installation": ("设备安装",),
    "Programming": ("编程", "程序设计", "软件编程"),
    "Operations Monitoring": ("运行监控",),
    "Operation and Control": ("操作控制",),
    "Equipment Maintenance": ("设备维护",),
    "Troubleshooting": ("故障排查",),
    "Repairing": ("维修",),
    "Quality Control Analysis": ("质量控制", "质量分析"),
    "Judgment and Decision Making": ("判断与决策", "决策"),
    "Systems Analysis": ("系统分析",),
    "Systems Evaluation": ("系统评估",),
    "Time Management": ("时间管理",),
    "Management of Financial Resources": ("财务资源管理", "预算管理"),
    "Management of Material Resources": ("物料管理", "资源配置"),
    "Management of Personnel Resources": ("人员管理", "团队管理"),
    "Python": ("Python3", "Python开发", "Python编程"),
    "Structured query language SQL": ("SQL", "SQL查询"),
    "Oracle Java": ("Java", "Java开发"),
    "Hypertext markup language HTML": ("HTML", "HTML5"),
    "Cascading style sheets CSS": ("CSS", "CSS3"),
    "Microsoft Excel": ("Excel", "电子表格"),
    "Microsoft Word": ("Word",),
    "Microsoft PowerPoint": ("PowerPoint", "PPT"),
    "Microsoft Office software": ("Office", "办公软件"),
    "Microsoft Power BI": ("PowerBI",),
    "Microsoft Project": ("MS Project",),
    "Microsoft SQL Server": ("SQL Server",),
    "Microsoft Azure software": ("Azure",),
    "Microsoft Visual Basic for Applications VBA": ("VBA",),
    "IBM SPSS Statistics": ("SPSS",),
    "The MathWorks MATLAB": ("MATLAB",),
    "Adobe Photoshop": ("Photoshop", "PS"),
    "Adobe Illustrator": ("Illustrator",),
    "Adobe InDesign": ("InDesign",),
    "Adobe Premiere Pro": ("Premiere",),
    "Adobe After Effects": ("AfterEffects", "AE"),
    "Atlassian JIRA": ("Jira",),
    "Google Analytics": ("GA",),
    "Google Angular": ("Angular",),
    "ESRI ArcGIS software": ("ArcGIS",),
    "Amazon Web Services AWS software": ("AWS",),
    "Oracle Database": ("Oracle数据库",),
    "SAP software": ("SAP",),
    "Salesforce software": ("Salesforce",),
    "Learning management system LMS": ("LMS", "学习管理系统"),
    "Data analysis software": ("数据分析",),
    "Scikit-learn": ("sklearn",),
    "Node.js": ("Nodejs",),
    "React": ("React.js", "Reactjs"),
    "RESTful API": ("REST API", "RESTful"),
}


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    path = Path(__file__).resolve().parents[1] / "data" / "occupations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _aliases(original: str) -> set[str]:
    return {normalize(original), *(normalize(value) for value in SKILL_ALIASES.get(original, ()))}


def _display(original: str) -> str:
    aliases = SKILL_ALIASES.get(original)
    return aliases[0] if aliases else original


def career_matches(profile: dict, limit: int = 10) -> dict:
    """Rank 1–10 real occupations using only explicitly confirmed skill names.

    60% measures supported input skills (at least 3 as denominator);
    40% rewards up to six supported skills. Aliases count as one skill.
    A source software example has weight 1 if in-demand, .75 if hot, else .5;
    essential/transferable skills use the official Importance rating / 5.
    Stars round this rule score / 20.
    No inferred credentials, personality labels, or claims about open vacancies.
    """
    snapshot = _snapshot()
    supplied = []
    for item in profile.get("skills", []):
        value = item if isinstance(item, str) else (item.get("normalized_name") or item.get("name")) if isinstance(item, dict) else None
        if isinstance(value, str) and value.strip():
            supplied.append(value.strip())
    canonical = {alias: normalize(original) for original in SKILL_ALIASES for alias in _aliases(original)}
    candidates = {canonical.get(name, name) for name in skill_names(supplied)}
    display = {canonical.get(normalize(value), normalize(value)): value for value in supplied}
    scored = []
    for occupation in snapshot["occupations"]:
        evidence: dict[str, float] = {}
        source_skills = []
        for skill in occupation["skills"]:
            source_skills.append((skill["original_name"], skill["importance"] / 5))
        for skill in occupation["software_skills"]:
            weight = 1.0 if skill["in_demand"] else .75 if skill["hot_technology"] else .5
            source_skills.append((skill["original_name"], weight))
        for original, weight in source_skills:
            for candidate in candidates & _aliases(original):
                evidence[candidate] = max(evidence.get(candidate, 0), weight)
        supported = sum(evidence.values())
        score = round(60 * supported / max(len(candidates), 3) + 40 * min(supported / 6, 1), 1) if candidates else 0.0
        matched = [display[name] for name in sorted(evidence)]
        gaps = []
        for original, _ in sorted(source_skills, key=lambda item: -item[1]):
            if not candidates & _aliases(original) and _display(original) not in gaps:
                gaps.append(_display(original))
            if len(gaps) == 5:
                break
        reason = (
            f"你填写的 {len(candidates)} 项技能中，有 {len(matched)} 项出现在这个职业的参考资料里：{'、'.join(matched)}。"
            if matched else "你填写的技能暂时没有与这个条目对应，记为 0 分。可以先阅读职业说明，再补充确实掌握的技能。"
        )
        scored.append({
            "code": occupation["code"],
            "title": occupation["title"],
            "original_title": occupation["original_title"],
            "description": occupation["description"],
            "source_url": occupation["source_url"],
            "score": score,
            "stars": min(5, int(score / 20 + .5)),
            "matched_skills": matched,
            "skill_gaps": gaps,
            "reason": reason,
            "_category": occupation["category"],
        })
    # Ties rotate across source categories, including when all evidence is absent.
    # This preserves descending scores without filling the list with one domain.
    by_score = defaultdict(list)
    for result in scored:
        by_score[result["score"]].append(result)
    ordered = []
    for score in sorted(by_score, reverse=True):
        categories = defaultdict(list)
        for result in by_score[score]:
            categories[result.pop("_category")].append(result)
        for index in range(max(map(len, categories.values()))):
            ordered.extend(items[index] for items in categories.values() if index < len(items))
    return {"catalog": {**snapshot["catalog"], "scoring_method": SCORING_METHOD}, "total": len(scored), "results": ordered[:max(1, min(int(limit), 10))]}
