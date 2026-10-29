"""Explainable five-star evidence completeness, never an ability assessment."""

import re
from collections.abc import Mapping


NOTICE = "星级仅表示已确认画像的信息完整度与简历原文证据覆盖：每满足一项公开检查得一星，最高五星。不是能力、人格、职业资格或录用概率测评。修改画像会重新计算。"


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return str(value).strip()


def _records(value: object) -> list[dict]:
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def profile_analysis(profile: dict, blocks: list[dict]) -> dict:
    sources = {str(item.get("block_id")): str(item.get("text", "")) for item in blocks}

    def quotes(records: list[dict]) -> list[str]:
        found = []
        for item in records:
            evidence = item.get("evidence")
            if not isinstance(evidence, Mapping):
                continue
            quote = _text(evidence.get("quote"))
            source = sources.get(str(evidence.get("block_id")), "")
            if quote and quote in source:
                found.append(quote[:280])
        return list(dict.fromkeys(found))[:3]

    def has(records: list[dict], *keys: str) -> bool:
        return any(_text(item.get(key)) for item in records for key in keys)

    education = _records(profile.get("education"))
    skills = _records(profile.get("skills"))
    projects = _records(profile.get("projects"))
    experience = _records(profile.get("experiences"))
    preferences = profile.get("preferences")
    preferences = dict(preferences) if isinstance(preferences, Mapping) else {}
    project_quotes = quotes(projects)
    experience_quotes = quotes(experience)
    skill_quotes = quotes(skills)
    dimensions = []

    def dimension(name: str, checks: list[tuple[str, bool]], evidence: list[str]) -> None:
        passed = [label for label, present in checks if present]
        missing = [label for label, present in checks if not present]
        dimensions.append({
            "name": name,
            "score": len(passed),
            "evidence": evidence,
            "note": "已具备：" + ("、".join(passed) or "暂无") + "；待补充：" + ("、".join(missing) or "本维度检查项完整"),
            "checks": [{"label": label, "passed": bool(present)} for label, present in checks],
        })

    dimension("教育描述", [
        ("教育记录", bool(education)), ("学校名称", has(education, "school", "institution")),
        ("学历层级", has(education, "degree", "学历")), ("专业名称", has(education, "major", "field")),
        ("起止或毕业时间", has(education, "graduation_year", "start_date", "end_date", "period", "dates")),
    ], quotes(education))
    dimension("技能证据", [
        ("技能记录", bool(skills)), ("技能名称", has(skills, "name")),
        ("规范技能名", has(skills, "normalized_name")), ("至少一条原文证据", bool(skill_quotes)),
        ("全部技能可定位原文", bool(skills) and all(bool(quotes([item])) for item in skills)),
    ], skill_quotes)
    dimension("项目表达", [
        ("项目记录", bool(projects)), ("项目名称", has(projects, "name", "title")),
        ("个人职责", has(projects, "role", "responsibilities", "contribution")),
        ("原文证据", bool(project_quotes)),
        ("原文包含结果或规模数字", any(re.search(r"\d[\d,.]*\s*(?:万|亿|条|个|张|项|人|次|%|％|小时|分钟|秒|倍)", quote) for quote in project_quotes)),
    ], project_quotes)
    dimension("实践经历", [
        ("经历记录", bool(experience)), ("机构名称", has(experience, "company", "organization")),
        ("角色或岗位", has(experience, "role", "position", "title")),
        ("起止时间", has(experience, "start_date", "end_date", "period", "dates")),
        ("原文证据", bool(experience_quotes)),
    ], experience_quotes)
    dimension("求职目标", [
        ("偏好记录", bool(preferences)),
        ("目标职业", bool(_text(preferences.get("roles") or preferences.get("target_roles") or preferences.get("job_titles")))),
        ("意向城市", bool(_text(preferences.get("cities")))),
        ("工作类型", bool(_text(preferences.get("employment_type") or preferences.get("job_type")))),
        ("到岗或毕业时间", bool(_text(preferences.get("availability") or preferences.get("start_date") or preferences.get("graduation_year")))),
    ], [])
    return {"dimensions": dimensions, "notice": NOTICE}
